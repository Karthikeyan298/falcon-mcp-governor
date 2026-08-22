import json

from app.database import Database, _DEFAULT_ALERT_RULES
from app.exceptions import NotFoundError
from app.formatting import clock_time
from app.repositories import AlertRepository, SettingsRepository


class AlertService:
    def __init__(self, database: Database):
        self._database = database

    def list_alerts(self, limit: int = 100) -> list[dict]:
        with self._database.connect() as conn:
            return [self._serialize(r) for r in AlertRepository(conn).list_recent(limit)]

    def count_unacknowledged(self) -> int:
        with self._database.connect() as conn:
            return AlertRepository(conn).count_unacknowledged()

    def acknowledge(self, alert_id: int, by: str) -> dict:
        now = self._database.now_iso()
        with self._database.connect() as conn:
            repo = AlertRepository(conn)
            if repo.get(alert_id) is None:
                raise NotFoundError(f'Alert #{alert_id} not found')
            repo.acknowledge(alert_id, by, now)
            return self._serialize(repo.get(alert_id))

    def get_rules(self) -> dict:
        with self._database.connect() as conn:
            raw = SettingsRepository(conn).get('alert_rules')
            if raw:
                try:
                    return json.loads(raw)
                except (ValueError, TypeError):
                    pass
            return _DEFAULT_ALERT_RULES

    def update_rules(self, rules: dict) -> dict:
        with self._database.connect() as conn:
            SettingsRepository(conn).set('alert_rules', json.dumps(rules))
        return rules

    @staticmethod
    def _serialize(row: dict) -> dict:
        return {
            'id': row['id'],
            'type': row['type'],
            'severity': row['severity'],
            'agent': row['agent'],
            'server': row['server'],
            'tool': row['tool'],
            'message': row['message'],
            'createdAt': clock_time(row['created_at']),
            'acknowledgedAt': clock_time(row['acknowledged_at']) if row['acknowledged_at'] else None,
            'acknowledgedBy': row['acknowledged_by'],
        }
