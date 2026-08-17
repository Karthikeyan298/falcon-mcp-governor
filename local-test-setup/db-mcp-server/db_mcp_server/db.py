"""SQLite access layer for the MCP CRUD server.

Table and column names come from tool arguments and can't be bound as SQL
parameters, so they're validated against a strict identifier pattern before
being interpolated into any statement. Values are always passed as bound
parameters.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_DB_PATH = Path(os.environ.get("DB_MCP_SQLITE_PATH", "./data/app.db"))


class InvalidIdentifierError(ValueError):
    pass


class UnknownTableError(ValueError):
    pass


def _validate_identifier(name: str, kind: str = "identifier") -> str:
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise InvalidIdentifierError(
            f"Invalid {kind} '{name}': must match [A-Za-z_][A-Za-z0-9_]*"
        )
    return name


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def _ensure_table_exists(conn: sqlite3.Connection, table: str) -> None:
    if table not in list_tables(conn):
        raise UnknownTableError(f"Table '{table}' does not exist")


def describe_table(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    _validate_identifier(table, "table name")
    _ensure_table_exists(conn, table)
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [dict(row) for row in rows]


def create_table(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    _validate_identifier(table, "table name")
    if not columns:
        raise ValueError("columns must contain at least one column definition")
    column_defs = []
    for col_name, col_type in columns.items():
        _validate_identifier(col_name, "column name")
        if not isinstance(col_type, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_ ]*$", col_type.strip()):
            raise InvalidIdentifierError(f"Invalid column type '{col_type}' for column '{col_name}'")
        column_defs.append(f'"{col_name}" {col_type}')
    ddl = f'CREATE TABLE IF NOT EXISTS "{table}" (\n  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  ' + ",\n  ".join(column_defs) + "\n)"
    conn.execute(ddl)
    conn.commit()


def create_record(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> int:
    _validate_identifier(table, "table name")
    _ensure_table_exists(conn, table)
    if not data:
        raise ValueError("data must contain at least one field")
    columns = list(data.keys())
    for col in columns:
        _validate_identifier(col, "column name")
    placeholders = ", ".join("?" for _ in columns)
    column_list = ", ".join(f'"{c}"' for c in columns)
    sql = f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})'
    cursor = conn.execute(sql, [data[c] for c in columns])
    conn.commit()
    return cursor.lastrowid


def read_records(
    conn: sqlite3.Connection,
    table: str,
    filters: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _validate_identifier(table, "table name")
    _ensure_table_exists(conn, table)
    limit = max(1, min(int(limit), 1000))
    offset = max(0, int(offset))

    sql = f'SELECT * FROM "{table}"'
    params: list[Any] = []
    if filters:
        clauses = []
        for col, val in filters.items():
            _validate_identifier(col, "column name")
            clauses.append(f'"{col}" = ?')
            params.append(val)
        sql += " WHERE " + " AND ".join(clauses)
    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def update_record(
    conn: sqlite3.Connection,
    table: str,
    record_id: int,
    data: dict[str, Any],
    id_column: str = "id",
) -> int:
    _validate_identifier(table, "table name")
    _validate_identifier(id_column, "column name")
    _ensure_table_exists(conn, table)
    if not data:
        raise ValueError("data must contain at least one field")
    for col in data:
        _validate_identifier(col, "column name")
    set_clause = ", ".join(f'"{c}" = ?' for c in data)
    sql = f'UPDATE "{table}" SET {set_clause} WHERE "{id_column}" = ?'
    params = list(data.values()) + [record_id]
    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor.rowcount


def delete_record(
    conn: sqlite3.Connection,
    table: str,
    record_id: int,
    id_column: str = "id",
) -> int:
    _validate_identifier(table, "table name")
    _validate_identifier(id_column, "column name")
    _ensure_table_exists(conn, table)
    sql = f'DELETE FROM "{table}" WHERE "{id_column}" = ?'
    cursor = conn.execute(sql, [record_id])
    conn.commit()
    return cursor.rowcount


def execute_select(conn: sqlite3.Connection, query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    stripped = query.strip().lower()
    if not stripped.startswith("select"):
        raise ValueError("execute_select only accepts SELECT statements")
    rows = conn.execute(query, params or []).fetchall()
    return [dict(row) for row in rows]
