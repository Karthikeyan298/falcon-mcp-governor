# DB MCP Server

This project exposes a minimal SQLite-backed MCP server that supports CRUD operations over HTTP.

## Features

- Create records
- Read records
- Update records
- Delete records
- List tables and query a database

## Run

```bash
python -m pip install -r requirements.txt
python -m db_mcp_server.server
```

By default, the server listens on `http://0.0.0.0:8000/mcp`.

## Example

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Notes

The server uses SQLite and stores data in `./data/app.db` by default.
