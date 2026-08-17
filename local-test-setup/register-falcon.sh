#!/usr/bin/env bash
# Registers the local-test-setup MCP servers and the story-creator agent
# against a running Falcon control plane, via its API. Idempotent: already
# -registered servers/agents are left alone rather than erroring.
#
# On success, the story-creator agent's one-time API key is written to
# local-test-setup/.env as MCP_AGENT_KEY, which docker compose picks up
# automatically for the story-backend service.
#
# Usage:
#   ./register-falcon.sh
#   FALCON_ADMIN_PASSWORD=... ./register-falcon.sh
#
# Env vars:
#   FALCON_URL             default: http://localhost:8000
#   FALCON_ADMIN_USER      default: admin
#   FALCON_ADMIN_PASSWORD  default: admin@123
#
# Login: tries FALCON_ADMIN_PASSWORD (or the admin@123 default) first. If
# that fails -- a brand-new Falcon DB has a random one-time password instead
# -- falls back to reading that one-time password from the backend
# container's logs, logs in with it, then rotates the password to
# FALCON_ADMIN_PASSWORD/admin@123 so subsequent runs can log in directly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FALCON_URL="${FALCON_URL:-http://localhost:8000}"
FALCON_ADMIN_USER="${FALCON_ADMIN_USER:-admin}"
FALCON_ADMIN_PASSWORD="${FALCON_ADMIN_PASSWORD:-admin@123}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

log() { echo "[register-falcon] $*"; }

wait_for_falcon() {
  log "Waiting for Falcon backend at $FALCON_URL ..."
  for _ in $(seq 1 30); do
    if curl -sf "$FALCON_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "Falcon backend never became healthy at $FALCON_URL" >&2
  exit 1
}

# Attempts a login with the given password; sets COOKIE_JAR on success.
# Returns non-zero (without exiting, due to `|| true` callers) on failure.
try_login() {
  local password="$1" status
  status="$(curl -s -o /tmp/register-falcon-login.json -w '%{http_code}' \
    -c "$COOKIE_JAR" -X POST "$FALCON_URL/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"username\":\"$FALCON_ADMIN_USER\",\"password\":\"$password\"}")"
  [ "$status" = "200" ]
}

# Reads the one-time bootstrap password the backend prints to its own logs
# the first time it creates the admin user (only present for a fresh DB).
bootstrap_password_from_logs() {
  docker compose -f "$SCRIPT_DIR/../docker-compose.yml" logs backend 2>/dev/null \
    | grep -oP '(?<=password: ).*' | tail -1 || true
}

login() {
  if try_login "$FALCON_ADMIN_PASSWORD"; then
    log "Logged in as $FALCON_ADMIN_USER."
    return
  fi

  log "Login with FALCON_ADMIN_PASSWORD failed; checking backend logs for a one-time bootstrap password..."
  local bootstrap_pw
  bootstrap_pw="$(bootstrap_password_from_logs)"
  if [ -z "$bootstrap_pw" ] || ! try_login "$bootstrap_pw"; then
    echo "Could not log in as $FALCON_ADMIN_USER with FALCON_ADMIN_PASSWORD, and no working one-time bootstrap password was found in the backend logs." >&2
    echo "Set FALCON_ADMIN_PASSWORD to the current admin password and re-run this script." >&2
    exit 1
  fi
  log "Logged in with the one-time bootstrap password; rotating it to the configured admin password..."

  local status
  status="$(curl -s -o /tmp/register-falcon-password.json -w '%{http_code}' \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" -X POST "$FALCON_URL/api/auth/password" \
    -H 'Content-Type: application/json' \
    -d "{\"current_password\":\"$bootstrap_pw\",\"new_password\":\"$FALCON_ADMIN_PASSWORD\"}")"
  if [ "$status" != "200" ]; then
    echo "Failed to rotate admin password ($status): $(cat /tmp/register-falcon-password.json)" >&2
    exit 1
  fi
  log "Admin password set to the configured FALCON_ADMIN_PASSWORD."
}

# Registers a server if it doesn't already exist. Idempotent.
upsert_server() {
  local slug="$1" name="$2" endpoint="$3"
  local status
  status="$(curl -s -o /tmp/register-falcon-server.json -w '%{http_code}' \
    -b "$COOKIE_JAR" -X POST "$FALCON_URL/api/servers" \
    -H 'Content-Type: application/json' \
    -d "{\"slug\":\"$slug\",\"name\":\"$name\",\"endpoint\":\"$endpoint\",\"trust\":\"Trusted\"}")"
  case "$status" in
    200|201) log "Registered server '$slug' -> $endpoint" ;;
    409) log "Server '$slug' already registered, updating its endpoint."
         curl -s -o /dev/null -b "$COOKIE_JAR" -X PUT "$FALCON_URL/api/servers/$slug" \
           -H 'Content-Type: application/json' \
           -d "{\"name\":\"$name\",\"endpoint\":\"$endpoint\",\"trust\":\"Trusted\"}" ;;
    *) echo "Failed to register server '$slug' ($status): $(cat /tmp/register-falcon-server.json)" >&2; exit 1 ;;
  esac
}

# Discovers tools on a registered server (populates its tool list/toolCount).
sync_server() {
  local slug="$1" status
  status="$(curl -s -o /tmp/register-falcon-sync.json -w '%{http_code}' \
    -b "$COOKIE_JAR" -X POST "$FALCON_URL/api/servers/$slug/sync")"
  if [ "$status" != "200" ]; then
    echo "Failed to sync server '$slug' ($status): $(cat /tmp/register-falcon-sync.json)" >&2
    exit 1
  fi
  log "Synced server '$slug' -> $(python3 -c "import json; print(json.load(open('/tmp/register-falcon-sync.json'))['toolCount'])") tools discovered."
}

# Registers the story-creator agent if it doesn't already exist. Writes its
# one-time API key to local-test-setup/.env. If it already exists, leaves
# any previously-written .env alone (the key can't be recovered).
upsert_agent() {
  local name="$1" owner="$2"
  local status
  status="$(curl -s -o /tmp/register-falcon-agent.json -w '%{http_code}' \
    -b "$COOKIE_JAR" -X POST "$FALCON_URL/api/agents" \
    -H 'Content-Type: application/json' \
    -d "{\"name\":\"$name\",\"owner\":\"$owner\",\"environment\":\"Local\",\"status\":\"Active\"}")"
  case "$status" in
    200|201)
      local api_key
      api_key="$(python3 -c "import json,sys; print(json.load(open('/tmp/register-falcon-agent.json'))['api_key'])")"
      local env_file="$SCRIPT_DIR/.env"
      grep -v '^MCP_AGENT_KEY=' "$env_file" 2>/dev/null > "$env_file.tmp" || true
      echo "MCP_AGENT_KEY=$api_key" >> "$env_file.tmp"
      mv "$env_file.tmp" "$env_file"
      log "Registered agent '$name' and wrote its API key to local-test-setup/.env."
      ;;
    409)
      log "Agent '$name' already registered; leaving existing local-test-setup/.env (if any) untouched."
      ;;
    *)
      echo "Failed to register agent '$name' ($status): $(cat /tmp/register-falcon-agent.json)" >&2
      exit 1
      ;;
  esac
}

# Deploys a policy that allows every tool (current and future) on the
# database and email-server MCP servers, via a "*" wildcard rule -- so the
# gateway doesn't block local-test-setup calls just because a tool isn't
# individually listed.
allow_all_tools() {
  local policy_json policy_yaml status
  policy_json="$(curl -s -b "$COOKIE_JAR" "$FALCON_URL/api/policy")"
  policy_yaml="$(python3 -c "
import json, sys, yaml

policy = yaml.safe_load(json.loads(sys.stdin.read())['yaml']) or {}
servers = policy.setdefault('servers', {})
servers['database'] = {'tools': {'*': {'action': 'allow'}}}
servers['email-server'] = {'tools': {'*': {'action': 'allow'}}}
print(json.dumps(yaml.dump(policy, sort_keys=False, default_flow_style=False)))
" <<< "$policy_json")"

  status="$(curl -s -o /tmp/register-falcon-policy.json -w '%{http_code}' \
    -b "$COOKIE_JAR" -X POST "$FALCON_URL/api/policies/deploy" \
    -H 'Content-Type: application/json' \
    -d "{\"yaml\":$policy_yaml}")"
  if [ "$status" != "200" ]; then
    echo "Failed to deploy policy ($status): $(cat /tmp/register-falcon-policy.json)" >&2
    exit 1
  fi
  log "Deployed policy: allow all tools on 'database' and 'email-server'."
}

wait_for_falcon
login
upsert_server database "DB MCP" "http://host.docker.internal:8001/mcp"
upsert_server email-server "Email MCP" "http://host.docker.internal:8002/mcp"
sync_server database
sync_server email-server
upsert_agent story-creator story-writer-agent
allow_all_tools
