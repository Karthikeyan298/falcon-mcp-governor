# Falcon — Usage Guide

Falcon is an MCP governance control plane: AI agents connect to Falcon instead
of connecting directly to your MCP servers (Jira, email, Kubernetes,
databases, ...). Every `tools/list` and `tools/call` an agent makes passes
through Falcon's policy engine and trust registry first, and the outcome is
written to an audit trail.

This guide covers running the app and using every feature in the UI/API as
they exist today. It reflects the current implementation, not the original
MVP design doc (`docs/mcp-governance-mvp-design.md`) — notably, the
human-approval flow described there has been removed; every decision is now
`allow` or `deny`.

## 1. Running it

### Option A: Docker Compose (recommended)

```bash
docker compose up -d --build
```

This builds and starts two containers:

- **backend** — FastAPI on `http://localhost:8000`, SQLite persisted in the
  named volume `falcon-db` (survives `docker compose down`; use
  `docker compose down -v` to wipe it).
- **frontend** — the Angular app built for production and served by nginx on
  `http://localhost:4200`.

On first boot (empty database), the backend prints a one-time default admin
password to its log — this is your only chance to see it:

```bash
docker compose logs backend | grep -A3 "created default admin user"
```

If you serve the frontend from anywhere other than `http://localhost:4200`,
set `FALCON_UI_ORIGINS` (comma-separated) before starting, or CORS will
reject the login request:

```bash
FALCON_UI_ORIGINS=http://localhost:5173 docker compose up -d --build
```

### Option B: run it directly

#### Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

- API docs (Swagger UI): http://localhost:8000/docs
- Health check: `GET /health`
- SQLite database file: `backend/data/control_plane.db` (created on first
  run; schema/migrations run automatically on startup)

The database starts **empty** — no demo agents, servers, or tools are
seeded. You build it up through the UI or API as described below.

#### Frontend (Angular)

```bash
cd ui/mcp-governance-ui
npm install
npm start   # ng serve, defaults to http://localhost:4200
```

The UI talks to the backend at `http://localhost:8000` (see `API_BASE` in
`src/app/api.service.ts`).

## 2. Logging in

Every `/api/*` route except `/api/auth/*` requires a logged-in session — the
UI shows a login screen until you sign in, and a direct `curl` against, say,
`/api/agents` gets a `401` without a valid session cookie. `/health` and the
real agent gateway (`/mcp/{slug}`, which uses its own `X-Agent-Key` auth —
see §7) are unaffected.

- **First login**: username `admin`, password from the one-time bootstrap
  message (backend log on first startup, or `docker compose logs backend`).
- **Session**: an HttpOnly cookie (`falcon_session`), valid 24 hours,
  checked server-side against the `sessions` table — deleting the row (or
  waiting it out) revokes it. If you lose an admin's password and no other
  admin account exists, delete the database to re-trigger bootstrap
  (Docker: `docker compose down -v`).

### 2.1 Changing your own password

**Account tab** (every logged-in user has this, not just admins) → **Change
password**, or `POST /api/auth/password` with
`{"current_password": ..., "new_password": ...}` (min. 8 characters). This
works for the `admin` account too — there's no separate admin-reset flow,
just log in as admin and use the same form. Changing your password
invalidates every other session for that account (all devices get signed
out) and immediately issues a fresh session for the request that changed
it, so you stay logged in where you made the change.

### 2.2 Creating other users (admin only)

**Users tab** (visible only to admins) → **Create user**, or
`POST /api/users` with `{"username": ..., "role": "admin" | "user"}`. Non-admins get a `403`. The response includes a one-time `temp_password` —
same rule as agent API keys: copy it now, it's never shown again. The new
user should change it via §2.1 on first login. There's no "regular user"
permission model yet beyond the role field itself — any logged-in user
(admin or not) can currently use every non-admin-only endpoint; only user
creation is admin-gated today.

## 3. Core concepts

| Concept | What it is |
|---|---|
| **Agent** | An identity representing an AI agent. Has an owner, environment, status (Active/Suspended), and an API key used to authenticate real gateway traffic. |
| **MCP server** | An upstream MCP server (Jira, email, a database, ...) registered with Falcon. Falcon proxies to it instead of agents connecting directly. |
| **Tool** | A capability discovered from an MCP server's `tools/list` (e.g. `send_email`, `delete_pod`). Each has a risk level (Low/Medium/High) and, once synced, its real MCP input schema. |
| **Trust registry** | Per-tool signature/publisher status: `Verified`, `Needs approval`, or `Revoked`. Revoked or unverified tools are denied regardless of policy. |
| **Policy** | A YAML document mapping `agent → server → tool → action (allow/deny)`, with optional per-parameter rules. This is the single source of truth for what's allowed. |
| **Audit trail** | An append-only log of every policy decision: who, what tool, what decision, why. |

## 4. Setting up an agent

**Agents tab → Register agent** (or `POST /api/agents`):

```json
{ "name": "story-creator", "owner": "alice", "environment": "Production", "tools_allowed": 0 }
```

The response includes a one-time `api_key` (e.g. `mcp_...`). **Copy it
immediately** — Falcon only stores its hash, so it can never be shown again.
If you lose it, delete the agent and register a new one.

This key is what the agent must send as the `X-Agent-Key` header when it
connects to the real gateway (see §7). Suspending an agent (toggle in the
Agents tab) immediately blocks it from authenticating, even with a valid key.

## 5. Registering and syncing an MCP server

**Servers tab → Add server** (or `POST /api/servers`):

```json
{ "slug": "email-server", "name": "Email MCP", "endpoint": "http://localhost:8002/mcp", "trust": "Trusted" }
```

- `endpoint` must be a live `http://`/`https://` MCP streamable-HTTP endpoint
  for sync and real proxying to work. Servers without one (or non-HTTP
  placeholder endpoints) can still hold manually-curated policy but can't be
  synced or proxied to.
- `trust` is the server-level default (`Trusted` or `Needs review`) applied
  to every tool discovered from it, unless a trust record already exists for
  that tool.

Click **Sync** (or `POST /api/servers/{slug}/sync`) to connect to the
endpoint's real `tools/list` and:
1. Replace Falcon's local tool list for that server with what the server
   actually reports (name, risk classification, and its real MCP
   `inputSchema`).
2. Upsert a trust record per tool (`Verified` if the server is `Trusted`,
   `Needs approval` otherwise).
3. Fill in a conservative default policy action for any newly-discovered
   tool that isn't already covered by policy — Low risk → `allow`,
   Medium/High risk → `deny` — without touching rules you've already set.

Re-sync any time the upstream server's tool list changes.

## 6. Writing policy

**Policies tab** shows the raw YAML (source of truth) plus a rule builder.

### YAML shape

```yaml
servers:                       # default rules, apply to every agent
  jira:
    tools:
      search_issues: { action: allow }
      "*": { action: deny }    # wildcard: fallback for any tool not listed
  email-server:
    tools:
      send_email:
        action: allow
        param_rules:            # optional, checked against call arguments
          - param: recipient
            not_endswith: "@company.com"
            decision: deny
            reason: External recipient blocked
agent_overrides:                # optional, keyed by agent name
  hr-agent:
    servers:
      email-server:
        tools:
          send_email: { action: deny }   # overrides the default for this agent only
```

- **Lookup order** for a given (agent, server, tool): agent-specific exact
  tool → agent-specific `"*"` → default exact tool → default `"*"` →
  default-deny.
- **`param_rules`** operators: `equals`, `not_equals`, `endswith`,
  `not_endswith`. A rule fires when *all* its operators match; a missing or
  empty parameter never triggers a rule. A firing `deny` rule always wins,
  even over an `allow` action.
- Every tool call is also gated by trust status first: `Revoked` or
  unverified (`Needs approval`) tools are denied before policy is even
  consulted for the param rules that would otherwise allow them.

### Rule builder

Pick an agent scope (blank = all agents), server, tool (`*` = all tools),
and `allow`/`deny`, then **Add rule to YAML** — this stages the change into
the YAML editor (`POST /api/policies/rule-preview`, pure text merge, no DB
write yet). Nothing takes effect until you click **Deploy**
(`POST /api/policies/deploy`), which validates the YAML and saves it.

## 7. Connecting a real agent to the gateway

Point your MCP client at `POST/GET/DELETE /mcp/{server_slug}` instead of the
upstream server directly, and include the agent's API key:

```
POST http://localhost:8000/mcp/email-server
X-Agent-Key: mcp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
```

- The `initialize` call is where identity is established: Falcon looks up
  the agent by the hash of `X-Agent-Key`, and that resolved agent name (not
  anything the client claims in `clientInfo.name`) is what policy is
  evaluated against for the rest of the session. Missing/invalid key or a
  suspended agent → `401`.
- `tools/list` is filtered — tools that would be denied for this agent are
  removed from the list before the client ever sees them.
- `tools/call` runs full policy evaluation; on `deny` the client gets a
  normal MCP tool result with `isError: true` and text
  `Blocked by policy: <reason>` (not an HTTP error — the call round-tripped
  fine, the *tool* was refused). On `allow`, Falcon proxies the call to the
  real upstream server and returns its actual result.
- Every `tools/call` (allow or deny) is written to the audit trail.
- Optional header `X-Agent-User`: a human username to attribute the call to
  in the audit log (defaults to the agent name).

If the upstream server is unreachable, Falcon returns `502` with a
`Could not reach MCP server at <endpoint>: ...` detail — that's a
downstream connectivity problem, not a policy decision.

## 8. Simulating a call from the UI (no real agent needed)

**Gateway tab → Simulate an agent call** runs the same policy engine and
writes to the same audit trail as a real call, without needing a live agent
connection or upstream server (`POST /api/gateway/invoke`). Useful for
testing policy changes.

Pick an agent, server, and tool; the form renders one input per parameter
from that tool's real MCP schema (after a sync) — object/array-typed
parameters get a JSON textarea. On `allow` it returns a canned success
message rather than actually calling the upstream server.

## 9. Trust registry

Each synced tool gets a trust record (**Overview → Signed tools**, or
**Servers tab**): `Verified`, `Needs approval`, or `Revoked`. This is
separate from policy — a tool with `action: allow` in policy is still denied
if its trust status is `Revoked` or `Needs approval`. There's currently no
UI to hand-edit an individual tool's trust status; it's set at sync time
from the server's `trust` field.

## 10. Audit trail

**Audit tab** (or `GET /api/audit`) lists every logged decision: time,
agent, server.tool, action, decision (Allowed/Denied), user, reason.
**Export log** downloads it as JSON. Policy deploys are logged too, under
agent `control-plane`.

## 11. API reference (quick index)

| Method & path | Purpose |
|---|---|
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` | Session auth; `login`/`me` are the only `/api/*` routes that don't themselves require an existing session |
| `POST /api/auth/password` | Change your own password (any logged-in user); rotates the session |
| `GET /api/users`, `POST /api/users` | List/create users — both admin-only; `POST` returns the one-time `temp_password` |
| `GET /api/dashboard` | Overview stats, tool policy matrix, signed tools, recent audit, current policy YAML |
| `GET/POST/DELETE /api/agents`, `POST /api/agents/{name}/toggle` | Manage agents; `POST` returns the one-time `api_key` |
| `GET/POST/PUT/DELETE /api/servers`, `POST /api/servers/{slug}/sync` | Manage MCP servers and trigger tool discovery |
| `GET /api/tools` | All discovered tools, including `inputSchema` |
| `GET /api/policy`, `POST /api/policies/rule-preview`, `POST /api/policies/deploy` | Read/stage/deploy policy YAML |
| `GET /api/audit` | Audit trail |
| `POST /api/gateway/invoke` | Simulate a call through the policy engine (UI demo path) |
| `POST/GET/DELETE /mcp/{slug}` | The real MCP gateway proxy — this is what agents actually connect to |

## 12. Common gotchas

- **"Failed to register agent" / weird DB errors after a pull**: the SQLite
  schema migrates additively on startup, but if you're seeing something
  stranger than a missing column, delete `backend/data/control_plane.db`
  and let it reinitialize (you'll lose local data).
- **A tool call returns a raw connection error instead of a policy
  message**: that means policy *allowed* the call and it reached the real
  upstream server, which itself failed (check the audit trail — if it says
  `Allowed`, the problem is downstream of Falcon, not a policy denial).
- **New tool doesn't show up**: sync the server again — tools are only
  known to Falcon after a sync of that server.
- **Rule builder "Add rule to YAML" then Deploy did nothing**: staging via
  the rule builder only edits the YAML text box locally; you still have to
  click **Deploy** to persist it.
- **Login works via `curl`/Swagger but not from the browser UI**: check
  `FALCON_UI_ORIGINS` matches the exact origin (scheme+host+port) the UI is
  served from — a credentialed cross-origin request silently fails CORS
  otherwise, and the browser console will show a CORS error, not a 401.
- **Lost the bootstrap admin password**: there's no reset flow; either log
  in as a different existing admin and create a new one, or wipe the
  database (`docker compose down -v`, or delete
  `backend/data/control_plane.db` locally) to re-trigger bootstrap.
