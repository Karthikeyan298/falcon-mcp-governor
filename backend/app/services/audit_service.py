import json

from app.database import Database
from app.formatting import clock_time
from app.repositories import AuditRepository


class AuditService:
    def __init__(self, database: Database):
        self._database = database

    def list_audit(self, limit: int = 200) -> list[dict]:
        with self._database.connect() as conn:
            rows = AuditRepository(conn).list_recent(limit)
            return [{
                'time': clock_time(r['created_at']), 'agent': r['agent'],
                'tool': f"{r['server']}.{r['tool']}" if r['server'] else r['tool'],
                'action': r['action'], 'decision': r['decision'], 'user': r['user'],
                'reason': r['reason'],
                'arguments': self._parse_args(r['arguments']),
            } for r in rows]

    @staticmethod
    def _parse_args(raw: str | None) -> dict | None:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None
