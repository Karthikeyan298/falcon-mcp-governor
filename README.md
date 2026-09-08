# Falcon

Falcon is a governance control plane for [MCP](https://modelcontextprotocol.io)
(Model Context Protocol) servers. AI agents connect to Falcon instead of
connecting directly to your MCP servers (Jira, email, Kubernetes, databases,
...) — every `tools/list` and `tools/call` an agent makes passes through
Falcon's policy engine and trust registry first, and the outcome is written
to an audit trail.

## Why

Once an AI agent has real credentials to internal systems, "which agent can
call which tool, with which parameters" stops being an afterthought. Falcon
centralizes that decision instead of leaving it to whatever each agent
happens to be configured with:

- **Agent identity** — every agent gets its own API key (shown once, stored
  only as a hash) and can be suspended instantly.
- **Policy-as-code** — a single YAML document maps `agent → server → tool →
  allow/deny`, with optional per-parameter rules (e.g. block `send_email`
  to any recipient outside `@company.com`).
- **Trust registry** — tools discovered from an MCP server are `Verified`,
  `Needs approval`, or `Revoked`; revoked/unverified tools are denied
  regardless of policy.
- **Audit trail** — every policy decision (who, what tool, allow/deny, why)
  is logged, exportable as JSON.
- **Encrypted credentials** — upstream MCP server credentials (bearer
  tokens, API keys, basic auth) are encrypted at rest.

## Quick start

```bash
./deploy.sh
```

This wraps `docker compose up -d --build` and starts two containers:

- **backend** — FastAPI on `http://localhost:8000`, SQLite persisted in the
  `falcon-db` volume
- **frontend** — Angular UI served by nginx on `http://localhost:4200`

Add `--with-local-test-setup` to also bring up example MCP servers (a db
server, an email server) and a demo agent registered against Falcon — useful
if you want something real to point a policy at without building your own
MCP server first:

```bash
./deploy.sh --with-local-test-setup
```

Tear down with `./deploy.sh down` (add `--with-local-test-setup` to tear
down both). If you don't need the local-test-setup wiring, plain
`docker compose up -d --build` works too — `deploy.sh` is a thin wrapper
around it.

The database starts empty. On first boot, the backend prints a one-time
admin password to its log:

```bash
docker compose logs backend | grep -A3 "created default admin user"
```

Log in at `http://localhost:4200` with username `admin` and that password.

If you serve the frontend from anywhere other than `http://localhost:4200`,
set `FALCON_UI_ORIGINS` first or CORS will reject the login request:

```bash
FALCON_UI_ORIGINS=http://localhost:5173 ./deploy.sh
```

Running the backend/frontend directly (without Docker), the full policy
YAML shape, the gateway protocol, and the API reference are all covered in
**[docs/usage-guide.md](docs/usage-guide.md)**.

## How it works

Point your MCP client at Falcon's gateway instead of the real server:

```
POST http://localhost:8000/mcp/{server_slug}
X-Agent-Key: mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Falcon resolves the agent from the key, filters `tools/list` down to what
that agent is allowed to see, evaluates every `tools/call` against policy
and trust status, and — on `allow` — proxies the call to the real upstream
server. Denied calls get a normal MCP result with `isError: true`, not an
HTTP error.

## Project layout

```
backend/                 FastAPI app (policy engine, gateway proxy, auth, audit)
ui/mcp-governance-ui/    Angular UI
local-test-setup/        Example MCP servers + a demo agent to try Falcon against
docs/                    Usage guide, MVP design doc, business overview
```

## Development

```bash
# backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000   # http://localhost:8000/docs for Swagger UI
pytest

# frontend
cd ui/mcp-governance-ui
npm install
npm start                                     # http://localhost:4200
```

## License

Apache License 2.0 with the [Commons Clause](https://commonsclause.com/)
restriction — see [LICENSE](LICENSE). Free to use, modify, and self-host,
including inside your own commercial products; the one thing withheld is
reselling or rebranding Falcon itself as a competing product.
