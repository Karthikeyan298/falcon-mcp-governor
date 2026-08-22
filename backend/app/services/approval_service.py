import json

from app.database import Database
from app.exceptions import NotFoundError
from app.formatting import clock_time
from app.mcp_client import McpClient
from app.policy_engine import PolicyEngine
from app.repositories import ApprovalRepository, AuditRepository, ServerRepository, SettingsRepository, TrustRepository
from app.services.anomaly_service import AnomalyDetector


class ApprovalService:
    def __init__(self, database: Database, policy_engine: PolicyEngine):
        self._database = database
        self._policy_engine = policy_engine

    def list_approvals(self, limit: int = 200) -> list[dict]:
        with self._database.connect() as conn:
            rows = ApprovalRepository(conn).list_recent(limit)
            return [self._serialize(r) for r in rows]

    def count_pending(self) -> int:
        with self._database.connect() as conn:
            return ApprovalRepository(conn).count_pending()

    def approve(self, approval_id: int, decision_by: str) -> dict:
        now = self._database.now_iso()
        with self._database.connect() as conn:
            repo = ApprovalRepository(conn)
            row = repo.get(approval_id)
            if row is None:
                raise NotFoundError(f'Approval #{approval_id} not found')
            if row['status'] != 'pending':
                raise NotFoundError(f'Approval #{approval_id} is already {row["status"]}')
            repo.decide(approval_id, 'approved', decision_by, now)

        # Execute the tool immediately so the agent does not need to retry
        self._execute_approved(dict(row), approval_id, decision_by)

        with self._database.connect() as conn:
            return self._serialize(ApprovalRepository(conn).get(approval_id))

    def _execute_approved(self, row: dict, approval_id: int, decision_by: str) -> None:
        """Re-evaluate the current policy then call the upstream MCP server."""
        with self._database.connect() as conn:
            server = ServerRepository(conn).get(row['server'])
            policy_yaml = SettingsRepository(conn).get('policy_yaml')
            trust_status = TrustRepository(conn).get_status(f"{row['server']}.{row['tool']}")

        if server is None or not server['endpoint'].startswith(('http://', 'https://')):
            return

        arguments = json.loads(row['arguments']) if row['arguments'] else {}

        # Re-evaluate the live policy: a param rule added after the approval was
        # requested must still be enforced (admin approval does not bypass policy).
        outcome = self._policy_engine.evaluate(
            policy_yaml=policy_yaml,
            server=row['server'],
            tool=row['tool'],
            params=arguments,
            trust_status=trust_status,
            agent=row['agent'],
        )

        if outcome.decision == 'deny':
            now = self._database.now_iso()
            with self._database.connect() as conn:
                AuditRepository(conn).log(
                    agent=row['agent'], server=row['server'], tool=row['tool'],
                    action='invoke', decision='Denied', user=decision_by,
                    reason=f'Blocked by current policy after approval: {outcome.reason}',
                    created_at=now,
                )
            return  # Leave as approved; admin can review and deny explicitly

        try:
            client = McpClient(server['endpoint'])
            upstream_session_id, _ = client.initialize_session()
            result = client.call(
                upstream_session_id,
                'tools/call',
                {'name': row['tool'], 'arguments': arguments},
                req_id=1,
            )
            result_text = json.dumps(result)
            now = self._database.now_iso()
            with self._database.connect() as conn:
                ApprovalRepository(conn).update_executed(approval_id, result_text, now)
                AuditRepository(conn).log(
                    agent=row['agent'], server=row['server'], tool=row['tool'],
                    action='invoke', decision='Allowed', user=decision_by,
                    reason=f'Approved and executed by {decision_by}',
                    created_at=now,
                )
        except Exception:  # noqa: BLE001
            pass  # Leave as approved; admin can retry

    def deny(self, approval_id: int, decision_by: str) -> dict:
        now = self._database.now_iso()
        with self._database.connect() as conn:
            repo = ApprovalRepository(conn)
            row = repo.get(approval_id)
            if row is None:
                raise NotFoundError(f'Approval #{approval_id} not found')
            if row['status'] != 'pending':
                raise NotFoundError(f'Approval #{approval_id} is already {row["status"]}')
            repo.decide(approval_id, 'denied', decision_by, now)
            AuditRepository(conn).log(
                agent=row['agent'], server=row['server'], tool=row['tool'],
                action='invoke', decision='Denied', user=decision_by,
                reason=f'Approval request denied by {decision_by}',
                created_at=now,
            )
            AnomalyDetector(self._database).check_with_conn(
                conn, agent=row['agent'], server=row['server'], tool=row['tool'],
                decision='Denied', now=now,
            )
            return self._serialize(repo.get(approval_id))

    @staticmethod
    def _serialize(row: dict) -> dict:
        try:
            args = json.loads(row['arguments']) if row['arguments'] else {}
        except (ValueError, TypeError):
            args = {}
        return {
            'id': row['id'],
            'agent': row['agent'],
            'server': row['server'],
            'tool': row['tool'],
            'arguments': args,
            'user': row['user'],
            'status': row['status'],
            'decisionBy': row['decision_by'],
            'decidedAt': clock_time(row['decided_at']) if row['decided_at'] else None,
            'createdAt': clock_time(row['created_at']),
            'result': row.get('result'),
        }
