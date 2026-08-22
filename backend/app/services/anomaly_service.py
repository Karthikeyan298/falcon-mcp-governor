import json
import sqlite3
from datetime import datetime, timedelta, timezone

from app.database import Database, _DEFAULT_ALERT_RULES
from app.repositories import AlertRepository


class AnomalyDetector:
    """Runs anomaly checks synchronously after each tool call, inside the
    caller's open connection so the just-written audit row is visible."""

    def __init__(self, database: Database):
        self._database = database

    def check_with_conn(
        self, conn: sqlite3.Connection, *,
        agent: str, server: str, tool: str, decision: str, now: str,
    ) -> None:
        rules = self._load_rules(conn)
        alert_repo = AlertRepository(conn)
        self._check_repeated_denials(conn, alert_repo, rules, agent, now)
        self._check_high_call_rate(conn, alert_repo, rules, agent, now)
        self._check_new_tool_attempt(conn, alert_repo, rules, agent, server, tool, now)
        self._check_approval_flood(conn, alert_repo, rules, agent, decision, now)

    @staticmethod
    def _load_rules(conn: sqlite3.Connection) -> dict:
        row = conn.execute("SELECT value FROM settings WHERE key = 'alert_rules'").fetchone()
        if row:
            try:
                return json.loads(row['value'])
            except (ValueError, TypeError):
                pass
        return _DEFAULT_ALERT_RULES

    @staticmethod
    def _cutoff(window_minutes: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()

    def _check_repeated_denials(self, conn, alert_repo, rules, agent, now):
        rule = rules.get('repeated_denials', {})
        if not rule.get('enabled', True):
            return
        threshold = int(rule.get('threshold', 5))
        window = int(rule.get('window_minutes', 10))
        severity = rule.get('severity', 'high')

        count = conn.execute(
            "SELECT COUNT(*) c FROM audit WHERE agent = ? AND decision = 'Denied' AND created_at >= ?",
            (agent, self._cutoff(window)),
        ).fetchone()['c']

        if count >= threshold and not alert_repo.exists_unacknowledged('repeated_denials', agent):
            alert_repo.create(
                type='repeated_denials', severity=severity, agent=agent, server=None, tool=None,
                message=f"Agent '{agent}' triggered {count} policy denials in the last {window} min.",
                created_at=now,
            )

    def _check_high_call_rate(self, conn, alert_repo, rules, agent, now):
        rule = rules.get('high_call_rate', {})
        if not rule.get('enabled', True):
            return
        threshold = int(rule.get('threshold', 30))
        window = int(rule.get('window_minutes', 1))
        severity = rule.get('severity', 'medium')

        count = conn.execute(
            'SELECT COUNT(*) c FROM audit WHERE agent = ? AND created_at >= ?',
            (agent, self._cutoff(window)),
        ).fetchone()['c']

        if count >= threshold and not alert_repo.exists_unacknowledged('high_call_rate', agent):
            alert_repo.create(
                type='high_call_rate', severity=severity, agent=agent, server=None, tool=None,
                message=f"Agent '{agent}' made {count} tool calls in {window} min — possible runaway loop.",
                created_at=now,
            )

    def _check_new_tool_attempt(self, conn, alert_repo, rules, agent, server, tool, now):
        rule = rules.get('new_tool_attempt', {})
        if not rule.get('enabled', True):
            return
        severity = rule.get('severity', 'low')

        count = conn.execute(
            'SELECT COUNT(*) c FROM audit WHERE agent = ? AND server = ? AND tool = ?',
            (agent, server, tool),
        ).fetchone()['c']

        if count == 1 and not alert_repo.has_alert_for_tool('new_tool_attempt', agent, server, tool):
            alert_repo.create(
                type='new_tool_attempt', severity=severity, agent=agent, server=server, tool=tool,
                message=f"Agent '{agent}' called a new tool for the first time: {server}.{tool}.",
                created_at=now,
            )

    def _check_approval_flood(self, conn, alert_repo, rules, agent, decision, now):
        if decision != 'Pending':
            return
        rule = rules.get('approval_flood', {})
        if not rule.get('enabled', True):
            return
        threshold = int(rule.get('threshold', 5))
        window = int(rule.get('window_minutes', 10))
        severity = rule.get('severity', 'medium')

        count = conn.execute(
            "SELECT COUNT(*) c FROM audit WHERE agent = ? AND decision = 'Pending' AND created_at >= ?",
            (agent, self._cutoff(window)),
        ).fetchone()['c']

        if count >= threshold and not alert_repo.exists_unacknowledged('approval_flood', agent):
            alert_repo.create(
                type='approval_flood', severity=severity, agent=agent, server=None, tool=None,
                message=f"Agent '{agent}' triggered {count} approval requests in {window} min.",
                created_at=now,
            )
