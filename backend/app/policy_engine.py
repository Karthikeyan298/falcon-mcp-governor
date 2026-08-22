"""Runtime policy evaluation for the MCP gateway.

`PolicyEngine` evaluates a tool invocation against the declarative YAML
policy and the signed tool trust registry, mirroring the enforcement order
described in the MVP design doc:

  1. trust/signature validation (revoked tools are rejected outright)
  2. parameter-level deny rules (e.g. external email recipients, prod namespaces)
  3. server/tool policy action (allow / deny)
  4. unverified-trust and default deny for anything not present in policy

There is no human-approval decision -- every call resolves to allow or deny.

Policy shape:

    servers:                     # default rules, apply to every agent
      jira:
        tools:
          search_issues: {action: allow}
          "*": {action: deny}    # wildcard: falls back for any tool not listed above
      email-server:
        tools:
          send_email:
            action: allow
            param_rules:          # optional, evaluated for this exact tool config
              - param: recipient
                not_endswith: "@company.com"
                decision: deny
                reason: External recipient blocked
    agent_overrides:              # optional, keyed by agent name
      hr-agent:
        servers:
          email:
            tools:
              send_email: {action: deny}   # overrides the default for this agent only

Lookup order for a given (agent, server, tool): an agent-specific exact-tool
config, then an agent-specific "*" (all tools) config, then the default
exact-tool config, then the default "*" config, then default-deny. An agent
with no entry under `agent_overrides` is governed purely by the default
`servers` block -- i.e. "all agents" unless a specific agent is called out.
Both `action` and `param_rules` come from whichever one tool config wins
that lookup -- there's no separate merge of param_rules across levels.

`param_rules` is a list of declarative checks against a single tool-call
parameter, each optionally firing a decision that can override or refine the
tool's base `action` (see `evaluate`'s docstring for exact precedence). This
keeps evaluation fully data-driven: adding or changing a parameter rule is a
policy YAML deploy, not a code change.
"""

from dataclasses import dataclass
from typing import Any, Callable

import yaml

ACTION_TO_DECISION = {
    'allow': 'allow',
    'deny': 'deny',
    'require_approval': 'require_approval',
}

RISK_TO_DEFAULT_ACTION = {
    'Low': 'allow',
    'Medium': 'deny',
    'High': 'deny',
}

# Comparison operators usable in a param_rules entry, e.g. {param: recipient, not_endswith: "@company.com"}.
_PARAM_RULE_OPERATORS: dict[str, Callable[[str, str], bool]] = {
    'equals': lambda value, target: value == target,
    'not_equals': lambda value, target: value != target,
    'contains': lambda value, target: target in value,
    'not_contains': lambda value, target: target not in value,
    'startswith': lambda value, target: value.startswith(target),
    'not_startswith': lambda value, target: not value.startswith(target),
    'endswith': lambda value, target: value.endswith(target),
    'not_endswith': lambda value, target: not value.endswith(target),
}


class InvalidPolicyError(ValueError):
    pass


@dataclass
class Decision:
    decision: str  # allow | deny
    reason: str


class PolicyEngine:
    """Stateless: every method takes the policy YAML text it needs and
    returns a result, so one instance can be safely shared across requests."""

    def parse(self, policy_yaml: str) -> dict:
        try:
            parsed = yaml.safe_load(policy_yaml) or {}
        except yaml.YAMLError as exc:
            raise InvalidPolicyError(f'Policy YAML is invalid: {exc}') from exc

        if not isinstance(parsed, dict) or 'servers' not in parsed:
            raise InvalidPolicyError("Policy must be a mapping with a top-level 'servers' key")

        return parsed

    def evaluate(
        self,
        *,
        policy_yaml: str,
        server: str,
        tool: str,
        params: dict[str, Any],
        trust_status: str | None,
        agent: str | None = None,
    ) -> Decision:
        if trust_status is None:
            return Decision('deny', 'Tool is not registered in the trust list')

        if trust_status == 'Revoked':
            return Decision('deny', 'Tool signature has been revoked')

        parsed_policy = self.parse(policy_yaml)
        tool_cfg = self._effective_tool_cfg(parsed_policy, agent, server, tool)

        param_decision = self._param_rule(tool_cfg, params)
        if param_decision is not None and param_decision.decision == 'deny':
            return param_decision

        action = tool_cfg.get('action')
        action = action if action in ACTION_TO_DECISION else None

        if action is None:
            return Decision('deny', 'No policy rule matches this agent/server/tool; default deny')

        if action == 'deny':
            return Decision('deny', 'Blocked by policy rule')

        if action == 'require_approval':
            return Decision('require_approval', 'Awaiting human approval before execution')

        if param_decision is not None:
            return param_decision

        if trust_status == 'Needs approval':
            return Decision('deny', 'Tool signature has not been verified yet')

        return Decision('allow', 'Policy allows this tool')

    def merge_default_actions(self, policy_yaml: str, server: str, tool_risks: dict[str, str]) -> str:
        """Add a conservative default action for any tool not already covered by policy.

        Existing rules are never overwritten -- this only fills gaps (e.g.
        tools a sync just discovered) with a risk-based default: Low ->
        allow, Medium/High -> deny.
        """
        parsed = self.parse(policy_yaml)
        tools_cfg = parsed.setdefault('servers', {}).setdefault(server, {}).setdefault('tools', {})

        for tool, risk in tool_risks.items():
            if tool in tools_cfg:
                continue
            tools_cfg[tool] = {'action': RISK_TO_DEFAULT_ACTION.get(risk, 'deny')}

        return self._dump(parsed)

    def upsert_rule(self, policy_yaml: str, *, agent: str | None, server: str, tool: str, action: str) -> str:
        """Set (creating or overwriting) a single rule's action -- the backing
        logic for the UI rule builder.

        `agent=None` (or empty) targets the default `servers` block, i.e. all
        agents. `tool='*'` targets every tool on that server via the
        wildcard. Only the `action` key is overwritten -- any `param_rules`
        already configured for that tool are preserved.
        """
        if action not in ACTION_TO_DECISION:
            raise InvalidPolicyError(f"Invalid action '{action}'; must be one of allow, deny, require_approval")

        parsed = self.parse(policy_yaml)

        if agent:
            servers_cfg = parsed.setdefault('agent_overrides', {}).setdefault(agent, {}).setdefault('servers', {})
        else:
            servers_cfg = parsed.setdefault('servers', {})

        tools_cfg = servers_cfg.setdefault(server, {}).setdefault('tools', {})
        tools_cfg.setdefault(tool, {})['action'] = action

        return self._dump(parsed)

    def upsert_param_rule(
        self, policy_yaml: str, *,
        agent: str | None, server: str, tool: str,
        param: str, operator: str, value: str, decision: str, reason: str,
    ) -> str:
        """Add or replace a single param_rule entry for the given (agent, server, tool).

        Rule identity is (param, operator) — submitting the same pair again updates
        the value/decision/reason in place. `tool='*'` is rejected because param rules
        must target a concrete tool to be meaningful.
        """
        if tool == '*':
            raise InvalidPolicyError("Parameter rules must target a specific tool, not the wildcard '*'")
        if not param:
            raise InvalidPolicyError("Parameter name is required")
        if operator not in _PARAM_RULE_OPERATORS:
            valid = ', '.join(_PARAM_RULE_OPERATORS)
            raise InvalidPolicyError(f"Invalid operator '{operator}'; must be one of {valid}")
        if decision not in ACTION_TO_DECISION:
            raise InvalidPolicyError(f"Invalid decision '{decision}'; must be one of allow, deny, require_approval")

        parsed = self.parse(policy_yaml)

        if agent:
            servers_cfg = parsed.setdefault('agent_overrides', {}).setdefault(agent, {}).setdefault('servers', {})
        else:
            servers_cfg = parsed.setdefault('servers', {})

        tool_cfg = servers_cfg.setdefault(server, {}).setdefault('tools', {}).setdefault(tool, {})
        if 'action' not in tool_cfg:
            tool_cfg['action'] = 'allow'  # safe default so the rule is reachable

        new_rule: dict[str, str] = {'param': param, operator: value, 'decision': decision}
        if reason:
            new_rule['reason'] = reason

        rules: list = tool_cfg.setdefault('param_rules', [])
        for i, existing in enumerate(rules):
            if existing.get('param') == param and operator in existing:
                rules[i] = new_rule
                return self._dump(parsed)

        rules.append(new_rule)
        return self._dump(parsed)

    @staticmethod
    def _dump(parsed_policy: dict) -> str:
        return yaml.dump(parsed_policy, sort_keys=False, default_flow_style=False)

    @staticmethod
    def _tool_cfg_from_servers_cfg(servers_cfg: dict, server: str, tool: str) -> dict | None:
        tools_cfg = (servers_cfg.get(server) or {}).get('tools') or {}
        tool_cfg = tools_cfg.get(tool)
        if tool_cfg is None:
            tool_cfg = tools_cfg.get('*')  # wildcard: matches any tool not listed explicitly
        return tool_cfg or None

    def _effective_tool_cfg(self, parsed_policy: dict, agent: str | None, server: str, tool: str) -> dict:
        """The single tool config (action + param_rules) that governs this
        call, per the agent-override-then-default lookup order."""
        if agent:
            agent_cfg = (parsed_policy.get('agent_overrides') or {}).get(agent) or {}
            agent_servers_cfg = agent_cfg.get('servers') or {}
            tool_cfg = self._tool_cfg_from_servers_cfg(agent_servers_cfg, server, tool)
            if tool_cfg is not None:
                return tool_cfg

        default_servers_cfg = parsed_policy.get('servers') or {}
        return self._tool_cfg_from_servers_cfg(default_servers_cfg, server, tool) or {}

    def _param_rule(self, tool_cfg: dict, params: dict[str, Any]) -> Decision | None:
        for rule in tool_cfg.get('param_rules') or []:
            if self._param_rule_matches(rule, params):
                param_name = rule.get('param', '')
                raw = params.get(param_name)
                ops = {op: rule[op] for op in _PARAM_RULE_OPERATORS if op in rule}
                ops_detail = ', '.join(f"{op}={v!r}" for op, v in ops.items())
                detail = f"param '{param_name}'={raw!r} matched {ops_detail}"
                base = rule.get('reason') or 'Blocked by parameter rule'
                return Decision(rule.get('decision', 'deny'), f"{base} [{detail}]")
        return None

    @staticmethod
    def _param_rule_matches(rule: dict, params: dict[str, Any]) -> bool:
        param_name = rule.get('param')
        if not param_name:
            return False

        raw = params.get(param_name)
        if raw is None:
            return False

        # List parameters (e.g. email 'to' field) are checked element-by-element;
        # the rule fires if any element satisfies all the operators in the rule.
        if isinstance(raw, list):
            values = [str(v) for v in raw if v is not None and str(v)]
        else:
            if not raw:  # empty string / falsy scalar → no trigger
                return False
            values = [str(raw)]

        if not values:
            return False

        matched_any_operator = False
        for op_name, op_fn in _PARAM_RULE_OPERATORS.items():
            if op_name in rule:
                matched_any_operator = True
                # For list params: rule fires if any element satisfies this operator
                if not any(op_fn(v, str(rule[op_name])) for v in values):
                    return False
        return matched_any_operator


_default_policy_engine = PolicyEngine()


def get_policy_engine() -> PolicyEngine:
    """FastAPI dependency provider. PolicyEngine is stateless, so one shared instance is fine."""
    return _default_policy_engine
