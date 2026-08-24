"""SQLite access for the control plane, wrapped in a `Database` class.

Callers get a connection via `Database.connect()`; repositories (see
`repositories.py`) are constructed around that connection per unit of work.
Using a class instead of a module of free functions means tests can build an
isolated `Database(tmp_path / "test.db")` and inject it via FastAPI's
`dependency_overrides`, instead of monkeypatching a module-level path.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.security import generate_temp_password, hash_api_key, hash_password

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'control_plane.db'

_DEFAULT_ALERT_RULES = {
    'repeated_denials': {'enabled': True, 'threshold': 5, 'window_minutes': 10, 'severity': 'high'},
    'high_call_rate':   {'enabled': True, 'threshold': 30, 'window_minutes': 1, 'severity': 'medium'},
    'new_tool_attempt': {'enabled': True, 'severity': 'low'},
    'approval_flood':   {'enabled': True, 'threshold': 5, 'window_minutes': 10, 'severity': 'medium'},
}

DEFAULT_POLICY_YAML = '''agent:
  name: production-support
servers:
  jira:
    tools:
      search_issues:
        action: allow
      create_issue:
        action: allow
      update_issue:
        action: deny
      delete_issue:
        action: deny
  email:
    tools:
      send_email:
        action: allow
        param_rules:
          - param: recipient
            not_endswith: "@company.com"
            decision: deny
            reason: External recipient blocked
      delete_email:
        action: deny
  kubernetes:
    tools:
      list_pods:
        action: allow
      delete_pod:
        action: deny
        param_rules:
          - param: namespace
            equals: production
            decision: deny
            reason: Production namespace requested'''

_SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS agents (
    name TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    environment TEXT NOT NULL,
    tools_allowed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Active',
    api_key_hash TEXT
);

CREATE TABLE IF NOT EXISTS servers (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    trust TEXT NOT NULL DEFAULT 'Trusted',
    last_synced TEXT NOT NULL,
    credentials TEXT
);

CREATE TABLE IF NOT EXISTS tools (
    server TEXT NOT NULL,
    name TEXT NOT NULL,
    risk TEXT NOT NULL,
    environment TEXT NOT NULL,
    input_schema TEXT,
    PRIMARY KEY (server, name)
);

CREATE TABLE IF NOT EXISTS trust_records (
    tool_key TEXT PRIMARY KEY,
    publisher TEXT NOT NULL,
    status TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    server TEXT,
    tool TEXT NOT NULL,
    action TEXT NOT NULL,
    decision TEXT NOT NULL,
    user TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'Active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    agent TEXT NOT NULL,
    server TEXT,
    tool TEXT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    acknowledged_at TEXT,
    acknowledged_by TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,
    server TEXT NOT NULL,
    tool TEXT NOT NULL,
    arguments TEXT,
    user TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    decision_by TEXT,
    decided_at TEXT,
    created_at TEXT NOT NULL,
    result TEXT
);
'''


class Database:
    """Owns one SQLite file: connection lifecycle, schema, and seed data."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA_SQL)
            self._migrate(conn)
            # `settings` (not `agents`) is the freshness signal: agents can
            # legitimately go back to zero rows (e.g. all deleted via the UI)
            # without the database being "unseeded".
            if conn.execute("SELECT COUNT(*) FROM settings WHERE key = 'policy_yaml'").fetchone()[0] == 0:
                self._seed(conn)
            self._bootstrap_admin(conn)

    @staticmethod
    def _bootstrap_admin(conn: sqlite3.Connection) -> None:
        """Creates a default `admin` user the first time the `users` table is
        empty (fresh DB, or every user was since deleted). The one-time
        password is only ever available here -- printed to the process log --
        since there's no logged-in admin yet to hand it to via the API."""
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0:
            return

        temp_password = generate_temp_password()
        conn.execute(
            'INSERT INTO users (username, password_hash, role, status, created_at) VALUES (?, ?, ?, ?, ?)',
            ('admin', hash_password(temp_password), 'admin', 'Active', Database.now_iso()),
        )
        print(
            '\n'
            '==================================================================\n'
            'Falcon: created default admin user.\n'
            f'  username: admin\n'
            f'  password: {temp_password}\n'
            'This password is shown only once -- log in and note it somewhere\n'
            'safe, or create a new admin user and deactivate this one.\n'
            '==================================================================\n'
        )

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Additive column migrations for DBs created before a schema change.
        `CREATE TABLE IF NOT EXISTS` above never alters an existing table."""
        agent_columns = {row['name'] for row in conn.execute('PRAGMA table_info(agents)')}
        if 'api_key_hash' not in agent_columns:
            conn.execute('ALTER TABLE agents ADD COLUMN api_key_hash TEXT')

        tool_columns = {row['name'] for row in conn.execute('PRAGMA table_info(tools)')}
        if 'input_schema' not in tool_columns:
            conn.execute('ALTER TABLE tools ADD COLUMN input_schema TEXT')

        server_columns = {row['name'] for row in conn.execute('PRAGMA table_info(servers)')}
        if 'credentials' not in server_columns:
            conn.execute('ALTER TABLE servers ADD COLUMN credentials TEXT')

        # Seed default alert rules on first run or upgrade from older schema.
        if conn.execute("SELECT COUNT(*) FROM settings WHERE key = 'alert_rules'").fetchone()[0] == 0:
            conn.execute("INSERT INTO settings (key, value) VALUES ('alert_rules', ?)", (json.dumps(_DEFAULT_ALERT_RULES),))

        # Backfill agents left over from before api_key_hash existed with the same
        # deterministic demo key pattern _seed() uses, so they keep working locally.
        for row in conn.execute('SELECT name FROM agents WHERE api_key_hash IS NULL'):
            conn.execute(
                'UPDATE agents SET api_key_hash = ? WHERE name = ?',
                (hash_api_key(f"demo-{row['name']}-key"), row['name']),
            )

    def _seed(self, conn: sqlite3.Connection) -> None:
        """Initializes the settings a fresh database needs to function
        (default policy YAML, deployment timestamp). No demo agents,
        servers, tools, trust records, audit entries, or approvals are
        inserted -- the app starts empty and is populated through the API."""
        now = self.now_iso()
        conn.execute("INSERT INTO settings (key, value) VALUES ('policy_yaml', ?)", (DEFAULT_POLICY_YAML,))
        conn.execute("INSERT INTO settings (key, value) VALUES ('last_deployment', ?)", (now,))


_default_database = Database()


def get_database() -> Database:
    """FastAPI dependency provider; overridden in tests for an isolated DB."""
    return _default_database
