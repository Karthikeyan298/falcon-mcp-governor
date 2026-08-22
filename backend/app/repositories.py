"""Data-access layer: one repository class per table.

Every repository wraps a single `sqlite3.Connection` (one unit of work,
handed out by `Database.connect()`) and exposes typed methods instead of raw
SQL, so nothing above this layer writes a query directly. Rows are returned
as plain `dict`s -- close enough to the JSON the API already returns that
adding a further per-entity dataclass layer would be pure ceremony.
"""

import sqlite3


class AgentRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM agents ORDER BY name').fetchall()
        return [dict(r) for r in rows]

    def get(self, name: str) -> dict | None:
        row = self._conn.execute('SELECT * FROM agents WHERE name = ?', (name,)).fetchone()
        return dict(row) if row else None

    def exists(self, name: str) -> bool:
        return self._conn.execute('SELECT 1 FROM agents WHERE name = ?', (name,)).fetchone() is not None

    def create(self, *, name: str, owner: str, environment: str, tools_allowed: int, status: str, api_key_hash: str) -> None:
        self._conn.execute(
            'INSERT INTO agents (name, owner, environment, tools_allowed, status, api_key_hash) VALUES (?, ?, ?, ?, ?, ?)',
            (name, owner, environment, tools_allowed, status, api_key_hash),
        )

    def get_by_api_key_hash(self, api_key_hash: str) -> dict | None:
        row = self._conn.execute('SELECT * FROM agents WHERE api_key_hash = ?', (api_key_hash,)).fetchone()
        return dict(row) if row else None

    def delete(self, name: str) -> None:
        self._conn.execute('DELETE FROM agents WHERE name = ?', (name,))

    def set_status(self, name: str, status: str) -> None:
        self._conn.execute('UPDATE agents SET status = ? WHERE name = ?', (status, name))


class ServerRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM servers ORDER BY name').fetchall()
        return [dict(r) for r in rows]

    def get(self, slug: str) -> dict | None:
        row = self._conn.execute('SELECT * FROM servers WHERE slug = ?', (slug,)).fetchone()
        return dict(row) if row else None

    def exists(self, slug: str) -> bool:
        return self._conn.execute('SELECT 1 FROM servers WHERE slug = ?', (slug,)).fetchone() is not None

    def display_name(self, slug: str) -> str:
        row = self._conn.execute('SELECT name FROM servers WHERE slug = ?', (slug,)).fetchone()
        return row['name'] if row else slug

    def create(self, *, slug: str, name: str, endpoint: str, trust: str, last_synced: str) -> None:
        self._conn.execute(
            'INSERT INTO servers (slug, name, endpoint, trust, last_synced) VALUES (?, ?, ?, ?, ?)',
            (slug, name, endpoint, trust, last_synced),
        )

    def update(self, slug: str, *, name: str, endpoint: str, trust: str) -> None:
        self._conn.execute(
            'UPDATE servers SET name = ?, endpoint = ?, trust = ? WHERE slug = ?',
            (name, endpoint, trust, slug),
        )

    def touch_last_synced(self, slug: str, iso_ts: str) -> None:
        self._conn.execute('UPDATE servers SET last_synced = ? WHERE slug = ?', (iso_ts, slug))

    def delete(self, slug: str) -> None:
        self._conn.execute('DELETE FROM servers WHERE slug = ?', (slug,))


class ToolRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM tools ORDER BY server, name').fetchall()
        return [dict(r) for r in rows]

    def list_for_server(self, server: str) -> list[dict]:
        rows = self._conn.execute(
            'SELECT server, name, risk, environment FROM tools WHERE server = ? ORDER BY name', (server,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, server: str, name: str) -> dict | None:
        row = self._conn.execute('SELECT * FROM tools WHERE server = ? AND name = ?', (server, name)).fetchone()
        return dict(row) if row else None

    def count_for_server(self, server: str) -> int:
        return self._conn.execute('SELECT COUNT(*) c FROM tools WHERE server = ?', (server,)).fetchone()['c']

    def delete_for_server(self, server: str) -> None:
        self._conn.execute('DELETE FROM tools WHERE server = ?', (server,))

    def add(self, *, server: str, name: str, risk: str, environment: str, input_schema: str | None = None) -> None:
        self._conn.execute(
            'INSERT INTO tools (server, name, risk, environment, input_schema) VALUES (?, ?, ?, ?, ?)',
            (server, name, risk, environment, input_schema),
        )


class TrustRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM trust_records ORDER BY tool_key').fetchall()
        return [dict(r) for r in rows]

    def get_status(self, tool_key: str) -> str | None:
        row = self._conn.execute('SELECT status FROM trust_records WHERE tool_key = ?', (tool_key,)).fetchone()
        return row['status'] if row else None

    def upsert(self, *, tool_key: str, publisher: str, status: str, hash_: str) -> None:
        self._conn.execute(
            'INSERT OR REPLACE INTO trust_records (tool_key, publisher, status, hash) VALUES (?, ?, ?, ?)',
            (tool_key, publisher, status, hash_),
        )

    def delete_many(self, tool_keys: list[str]) -> None:
        if tool_keys:
            self._conn.executemany('DELETE FROM trust_records WHERE tool_key = ?', [(k,) for k in tool_keys])

    def count_verified(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM trust_records WHERE status = 'Verified'").fetchone()['c']


class AuditRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_recent(self, limit: int) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def count_total(self) -> int:
        return self._conn.execute('SELECT COUNT(*) c FROM audit').fetchone()['c']

    def count_denied(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM audit WHERE decision = 'Denied'").fetchone()['c']

    def log(
        self, *, agent: str, server: str | None, tool: str, action: str,
        decision: str, user: str, reason: str | None, created_at: str,
    ) -> None:
        self._conn.execute(
            'INSERT INTO audit (agent, server, tool, action, decision, user, reason, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (agent, server, tool, action, decision, user, reason, created_at),
        )


class SettingsRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
        return row['value'] if row else default

    def set(self, key: str, value: str) -> None:
        self._conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))


class UserRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def list_all(self) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM users ORDER BY username').fetchall()
        return [dict(r) for r in rows]

    def get(self, user_id: int) -> dict | None:
        row = self._conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        return dict(row) if row else None

    def get_by_username(self, username: str) -> dict | None:
        row = self._conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return dict(row) if row else None

    def exists(self, username: str) -> bool:
        return self._conn.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone() is not None

    def create(self, *, username: str, password_hash: str, role: str, status: str, created_at: str) -> int:
        cur = self._conn.execute(
            'INSERT INTO users (username, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?)',
            (username, password_hash, role, status, created_at),
        )
        return cur.lastrowid

    def set_status(self, user_id: int, status: str) -> None:
        self._conn.execute('UPDATE users SET status = ? WHERE id = ?', (status, user_id))

    def set_password_hash(self, user_id: int, password_hash: str) -> None:
        self._conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))

    def delete(self, user_id: int) -> None:
        self._conn.execute('DELETE FROM users WHERE id = ?', (user_id,))


class AlertRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(self, *, type: str, severity: str, agent: str, server: str | None, tool: str | None, message: str, created_at: str) -> int:
        cur = self._conn.execute(
            'INSERT INTO alerts (type, severity, agent, server, tool, message, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (type, severity, agent, server, tool, message, created_at),
        )
        return cur.lastrowid

    def list_recent(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def count_unacknowledged(self) -> int:
        return self._conn.execute('SELECT COUNT(*) c FROM alerts WHERE acknowledged_at IS NULL').fetchone()['c']

    def get(self, alert_id: int) -> dict | None:
        row = self._conn.execute('SELECT * FROM alerts WHERE id = ?', (alert_id,)).fetchone()
        return dict(row) if row else None

    def acknowledge(self, alert_id: int, by: str, at: str) -> None:
        self._conn.execute(
            'UPDATE alerts SET acknowledged_at = ?, acknowledged_by = ? WHERE id = ?',
            (at, by, alert_id),
        )

    def exists_unacknowledged(self, alert_type: str, agent: str) -> bool:
        return self._conn.execute(
            'SELECT 1 FROM alerts WHERE type = ? AND agent = ? AND acknowledged_at IS NULL',
            (alert_type, agent),
        ).fetchone() is not None

    def has_alert_for_tool(self, alert_type: str, agent: str, server: str, tool: str) -> bool:
        return self._conn.execute(
            'SELECT 1 FROM alerts WHERE type = ? AND agent = ? AND server = ? AND tool = ?',
            (alert_type, agent, server, tool),
        ).fetchone() is not None


class ApprovalRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(self, *, agent: str, server: str, tool: str, arguments: str | None, user: str, created_at: str) -> int:
        cur = self._conn.execute(
            'INSERT INTO approvals (agent, server, tool, arguments, user, created_at) VALUES (?, ?, ?, ?, ?, ?)',
            (agent, server, tool, arguments, user, created_at),
        )
        return cur.lastrowid

    def get(self, approval_id: int) -> dict | None:
        row = self._conn.execute('SELECT * FROM approvals WHERE id = ?', (approval_id,)).fetchone()
        return dict(row) if row else None

    def list_recent(self, limit: int = 200) -> list[dict]:
        rows = self._conn.execute('SELECT * FROM approvals ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [dict(r) for r in rows]

    def count_pending(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM approvals WHERE status = 'pending'").fetchone()['c']

    def decide(self, approval_id: int, status: str, decision_by: str, decided_at: str) -> None:
        self._conn.execute(
            'UPDATE approvals SET status = ?, decision_by = ?, decided_at = ? WHERE id = ?',
            (status, decision_by, decided_at, approval_id),
        )

    def update_executed(self, approval_id: int, result: str, executed_at: str) -> None:
        self._conn.execute(
            "UPDATE approvals SET status = 'executed', result = ?, decided_at = ? WHERE id = ?",
            (result, executed_at, approval_id),
        )


class SessionRepository:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def create(self, *, token_hash: str, user_id: int, created_at: str, expires_at: str) -> None:
        self._conn.execute(
            'INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)',
            (token_hash, user_id, created_at, expires_at),
        )

    def get_with_user(self, token_hash: str) -> dict | None:
        row = self._conn.execute(
            'SELECT s.expires_at, u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?',
            (token_hash,),
        ).fetchone()
        return dict(row) if row else None

    def delete(self, token_hash: str) -> None:
        self._conn.execute('DELETE FROM sessions WHERE token_hash = ?', (token_hash,))

    def delete_for_user(self, user_id: int) -> None:
        self._conn.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
