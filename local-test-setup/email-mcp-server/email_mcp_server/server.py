"""MCP server exposing email send/read tools over HTTP (SMTP + IMAP)."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from mcp.server.mcpserver import MCPServer

from email_mcp_server import mailer

HOST = os.environ.get("EMAIL_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("EMAIL_MCP_PORT", "8002"))

mcp = MCPServer(
    name="email-mcp-server",
    instructions=(
        "Sends email via SMTP and reads/searches a mailbox via IMAP. "
        "Credentials are read from environment variables (see .env.example); "
        "call list_folders first if unsure which folder to read from."
    ),
)


def _settings() -> mailer.EmailSettings:
    return mailer.EmailSettings.from_env()


@mcp.tool(description="Send an email via SMTP.")
def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
    html: bool = False,
) -> dict[str, Any]:
    return mailer.send_email(_settings(), to=to, subject=subject, body=body, cc=cc, bcc=bcc, html=html)


@mcp.tool(description="List mailbox folders available over IMAP.")
def list_folders() -> list[str]:
    return mailer.list_folders(_settings())


@mcp.tool(description="List recent messages in a folder (headers only, no body).")
def list_messages(folder: str = "INBOX", limit: int = 20, unseen_only: bool = False) -> list[dict[str, Any]]:
    return mailer.list_messages(_settings(), folder=folder, limit=limit, unseen_only=unseen_only)


@mcp.tool(description="Read the full content (headers + body) of a single message by its IMAP id.")
def read_message(message_id: str, folder: str = "INBOX") -> dict[str, Any]:
    return mailer.read_message(_settings(), message_id=message_id, folder=folder)


@mcp.tool(description="Search a folder for messages containing the given text.")
def search_messages(query: str, folder: str = "INBOX", limit: int = 20) -> list[dict[str, Any]]:
    return mailer.search_messages(_settings(), query=query, folder=folder, limit=limit)


def main() -> None:
    mcp.run(transport="streamable-http", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
