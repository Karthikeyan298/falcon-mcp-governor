"""MCP server exposing CRUD operations over a SQLite database via HTTP."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.mcpserver import MCPServer

from db_mcp_server import db

DB_PATH = db.DEFAULT_DB_PATH
HOST = os.environ.get("DB_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("DB_MCP_PORT", "8000"))

mcp = MCPServer(
    name="db-mcp-server",
    instructions=(
        "Provides CRUD tools over a SQLite database. Call list_tables or "
        "describe_table first to discover schema before reading or writing."
    ),
)


def _conn():
    return db.get_connection(DB_PATH)


@mcp.tool(description="List all tables in the database.")
def list_tables() -> list[str]:
    with _conn() as conn:
        return db.list_tables(conn)


@mcp.tool(description="Describe the columns of a table (name, type, nullability, default, pk).")
def describe_table(table: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        return db.describe_table(conn, table)


@mcp.tool(description="Create a new table with the given columns (a primary key 'id' column is added automatically).")
def create_table(table: str, columns: dict[str, str]) -> dict[str, str]:
    with _conn() as conn:
        db.create_table(conn, table, columns)
    return {"status": "created", "table": table}


@mcp.tool(description="Insert a new record into a table. Returns the new record's id.")
def create_record(table: str, data: dict[str, Any]) -> dict[str, Any]:
    with _conn() as conn:
        new_id = db.create_record(conn, table, data)
    return {"id": new_id}


@mcp.tool(description="Read records from a table, optionally filtered by exact-match column values.")
def read_records(
    table: str,
    filters: dict[str, Any] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with _conn() as conn:
        return db.read_records(conn, table, filters=filters, limit=limit, offset=offset)


@mcp.tool(description="Update an existing record by id. Only the provided fields are changed.")
def update_record(table: str, id: int, data: dict[str, Any]) -> dict[str, Any]:
    with _conn() as conn:
        rows_updated = db.update_record(conn, table, id, data)
    return {"rows_updated": rows_updated}


@mcp.tool(description="Delete a record from a table by id.")
def delete_record(table: str, id: int) -> dict[str, Any]:
    with _conn() as conn:
        rows_deleted = db.delete_record(conn, table, id)
    return {"rows_deleted": rows_deleted}


@mcp.tool(description="Run a read-only SELECT query with optional bound parameters.")
def execute_query(query: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    with _conn() as conn:
        return db.execute_select(conn, query, params)


def main() -> None:
    mcp.run(transport="streamable-http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
