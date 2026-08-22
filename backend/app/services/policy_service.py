from app.database import Database
from app.formatting import policy_status_label, relative_time
from app.policy_engine import InvalidPolicyError, PolicyEngine
from app.repositories import AuditRepository, ServerRepository, SettingsRepository, ToolRepository, TrustRepository


class PolicyService:
    def __init__(self, database: Database, policy_engine: PolicyEngine):
        self._database = database
        self._policy_engine = policy_engine

    def tool_matrix(self, agent: str | None = None) -> list[dict]:
        with self._database.connect() as conn:
            policy_yaml = SettingsRepository(conn).get('policy_yaml')
            tools = ToolRepository(conn).list_all()
            servers_repo = ServerRepository(conn)
            trust_repo = TrustRepository(conn)

            rows = []
            for t in tools:
                trust_status = trust_repo.get_status(f"{t['server']}.{t['name']}")
                try:
                    outcome = self._policy_engine.evaluate(
                        policy_yaml=policy_yaml, server=t['server'], tool=t['name'],
                        params={}, trust_status=trust_status, agent=agent,
                    )
                    status = policy_status_label(outcome.decision)
                except InvalidPolicyError:
                    status = 'Allowed'
                rows.append({
                    'name': t['name'],
                    'server': servers_repo.display_name(t['server']),
                    'serverSlug': t['server'],
                    'status': status,
                    'signed': trust_status == 'Verified',
                    'risk': t['risk'],
                    'environment': t['environment'],
                })
            return rows

    def get_policy(self) -> dict:
        with self._database.connect() as conn:
            settings = SettingsRepository(conn)
            return {'yaml': settings.get('policy_yaml'), 'lastDeployment': relative_time(settings.get('last_deployment'))}

    def preview_param_rule(
        self, *, yaml_text: str, agent: str | None, server: str, tool: str,
        param: str, operator: str, value: str, decision: str, reason: str,
    ) -> str:
        return self._policy_engine.upsert_param_rule(
            yaml_text, agent=agent or None, server=server, tool=tool,
            param=param, operator=operator, value=value, decision=decision, reason=reason,
        )

    def preview_rule(self, *, yaml_text: str, agent: str | None, server: str, tool: str, action: str) -> str:
        """Stateless: merges one rule into the given YAML and returns the
        result without touching the DB, so the UI rule builder can stage it
        for review before Deploy is clicked. Raises InvalidPolicyError (-> 422)."""
        return self._policy_engine.upsert_rule(yaml_text, agent=agent or None, server=server, tool=tool or '*', action=action)

    def deploy(self, yaml_text: str | None) -> None:
        with self._database.connect() as conn:
            settings = SettingsRepository(conn)
            if yaml_text is not None:
                self._policy_engine.parse(yaml_text)  # raises InvalidPolicyError (-> 422) if malformed
                settings.set('policy_yaml', yaml_text)

            now = self._database.now_iso()
            settings.set('last_deployment', now)
            AuditRepository(conn).log(
                agent='control-plane', server=None, tool='policy.deploy', action='deploy',
                decision='Allowed', user='platform-admin', reason='Policy deployed to gateway', created_at=now,
            )
