from app.database import Database
from app.exceptions import NotFoundError
from app.formatting import decision_label
from app.policy_engine import PolicyEngine
from app.repositories import AuditRepository, ServerRepository, SettingsRepository, ToolRepository, TrustRepository
from app.services.anomaly_service import AnomalyDetector


class GatewayInvokeService:
    """Backs `POST /api/gateway/invoke` -- the REST 'simulate an agent call'
    path used by the dashboard. Evaluates policy and logs the outcome; on
    `allow` it returns a canned success message rather than calling a real
    MCP server (that's what the real `/mcp/{slug}` proxy is for)."""

    def __init__(self, database: Database, policy_engine: PolicyEngine):
        self._database = database
        self._policy_engine = policy_engine

    def invoke(self, *, agent: str, server: str, tool: str, user: str, params: dict) -> dict:
        with self._database.connect() as conn:
            settings = SettingsRepository(conn)
            servers_repo = ServerRepository(conn)
            tools_repo = ToolRepository(conn)
            trust_repo = TrustRepository(conn)
            audit_repo = AuditRepository(conn)

            if servers_repo.get(server) is None:
                raise NotFoundError('Unknown MCP server')

            if tools_repo.get(server, tool) is None:
                raise NotFoundError('Unknown tool for this server')

            outcome = self._policy_engine.evaluate(
                policy_yaml=settings.get('policy_yaml'), server=server, tool=tool, params=params,
                trust_status=trust_repo.get_status(f'{server}.{tool}'), agent=agent,
            )  # InvalidPolicyError propagates -> 422 via router's exception handler

            label = decision_label(outcome.decision)
            now = self._database.now_iso()
            audit_repo.log(
                agent=agent, server=server, tool=tool, action='invoke',
                decision=label, user=user, reason=outcome.reason, created_at=now,
            )

            AnomalyDetector(self._database).check_with_conn(
                conn, agent=agent, server=server, tool=tool, decision=label, now=now,
            )

            result = None
            if outcome.decision == 'allow':
                result = {'ok': True, 'message': f'{server}.{tool} executed successfully'}

            return {'decision': outcome.decision, 'decisionLabel': label, 'reason': outcome.reason, 'result': result}
