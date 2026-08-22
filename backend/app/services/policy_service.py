from app.database import Database
from app.formatting import relative_time
from app.policy_engine import PolicyEngine
from app.repositories import AuditRepository, SettingsRepository


class PolicyService:
    def __init__(self, database: Database, policy_engine: PolicyEngine):
        self._database = database
        self._policy_engine = policy_engine

    def get_policy(self) -> dict:
        with self._database.connect() as conn:
            settings = SettingsRepository(conn)
            return {'yaml': settings.get('policy_yaml'), 'lastDeployment': relative_time(settings.get('last_deployment'))}

    def preview_rule(self, *, yaml_text: str, agent: str | None, server: str, tool: str, action: str) -> str:
        """Stateless: merges one rule into the given YAML and returns the
        result without touching the DB, so the UI rule builder can stage it
        for review before Deploy is clicked. Raises InvalidPolicyError (-> 422)."""
        return self._policy_engine.upsert_rule(yaml_text, agent=agent or None, server=server, tool=tool or '*', action=action)

    def preview_param_rule(
        self, *, yaml_text: str, agent: str | None, server: str, tool: str,
        param: str, operator: str, value: str, decision: str, reason: str,
    ) -> str:
        return self._policy_engine.upsert_param_rule(
            yaml_text, agent=agent or None, server=server, tool=tool,
            param=param, operator=operator, value=value, decision=decision, reason=reason,
        )

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
