# Email MCP Server

Exposes email send (SMTP) and read/search (IMAP) operations as MCP tools over HTTP.

## Features

- `send_email` — send a message via SMTP
- `list_folders` — list IMAP mailbox folders
- `list_messages` — list recent message headers in a folder
- `read_message` — fetch full headers + body for one message
- `search_messages` — full-text search within a folder

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in real SMTP/IMAP credentials
```

For Gmail, use an [App Password](https://myaccount.google.com/apppasswords) rather than your account password, and enable IMAP access in Gmail settings.

## Run

```bash
python -m email_mcp_server.server
```

By default the server listens on `http://0.0.0.0:8002/mcp`. Override with `EMAIL_MCP_HOST` / `EMAIL_MCP_PORT`.

## Example

```bash
curl -X POST http://localhost:8002/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Notes

Credentials are loaded from `.env` (gitignored) via `python-dotenv`. Never commit `.env`.
