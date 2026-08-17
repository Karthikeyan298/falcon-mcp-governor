from app.database import Database
from app.formatting import clock_time, decision_label, relative_time
from app.policy_engine import PolicyEngine
from app.repositories import AuditRepository, ServerRepository, SettingsRepository, ToolRepository, TrustRepository


class DashboardService:
    """Aggregates data for the single `GET /api/dashboard` payload the UI's Overview tab renders."""

    def __init__(self, database: Database, policy_engine: PolicyEngine):
        self._database = database
        self._policy_engine = policy_engine

    def get_dashboard(self) -> dict:
        with self._database.connect() as conn:
            settings = SettingsRepository(conn)
            tools_repo = ToolRepository(conn)
            trust_repo = TrustRepository(conn)
            audit_repo = AuditRepository(conn)
            servers_repo = ServerRepository(conn)

            policy_yaml = settings.get('policy_yaml')

            tool_policies = []
            for t in tools_repo.list_all():
                trust_status = trust_repo.get_status(f"{t['server']}.{t['name']}")
                decision = self._policy_engine.evaluate(
                    policy_yaml=policy_yaml, server=t['server'], tool=t['name'], params={}, trust_status=trust_status,
                )
                tool_policies.append({
                    'name': t['name'],
                    'server': servers_repo.display_name(t['server']),
                    'status': decision_label(decision.decision),
                    'signed': trust_status == 'Verified',
                    'risk': t['risk'],
                    'environment': t['environment'],
                })

            audit_trail = [{
                'time': clock_time(a['created_at']), 'agent': a['agent'],
                'tool': f"{a['server']}.{a['tool']}" if a['server'] else a['tool'],
                'action': a['action'], 'decision': a['decision'], 'user': a['user'],
            } for a in audit_repo.list_recent(50)]

            signed_tools = [{
                'name': r['tool_key'], 'publisher': r['publisher'], 'status': r['status'], 'hash': r['hash'],
            } for r in trust_repo.list_all()]

            stats = [
                {'label': 'Trusted tools', 'value': str(trust_repo.count_verified()), 'delta': ''},
                {'label': 'Blocked requests', 'value': str(audit_repo.count_denied()), 'delta': ''},
                {'label': 'Audit coverage', 'value': '100%' if audit_repo.count_total() else '0%', 'delta': ''},
            ]

            return {
                'lastDeployment': relative_time(settings.get('last_deployment')),
                'stats': stats,
                'toolPolicies': tool_policies,
                'auditTrail': audit_trail,
                'signedTools': signed_tools,
                'policyYaml': policy_yaml,
            }
