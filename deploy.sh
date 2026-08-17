#!/usr/bin/env bash
# Deploy the falcon control plane (backend + frontend), optionally alongside
# the local-test-setup stack (db-mcp-server, email-mcp-server, mailhog,
# story-writer-agent).
#
# When run with --with-local-test-setup, also registers the local-test-setup
# MCP servers and the story-creator agent against Falcon via its API (see
# local-test-setup/register-falcon.sh) before bringing up the rest of the
# stack, so story-backend starts with a valid MCP_AGENT_KEY already in
# local-test-setup/.env.
#
# Usage:
#   ./deploy.sh                          # falcon only
#   ./deploy.sh --with-local-test-setup  # falcon + local-test-setup (+ API registration)
#   ./deploy.sh down                     # tear down falcon (add --with-local-test-setup to tear down both)
#
# Env vars (only used with --with-local-test-setup on `up`):
#   FALCON_ADMIN_PASSWORD  admin password to register with, default: admin@123.
#                          On a brand-new Falcon DB (random one-time bootstrap
#                          password) the admin password is auto-rotated to
#                          this value; see local-test-setup/register-falcon.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FALCON_DIR="$SCRIPT_DIR"
TEST_SETUP_DIR="$SCRIPT_DIR/local-test-setup"

ACTION="up"
WITH_LOCAL_TEST_SETUP=false

for arg in "$@"; do
  case "$arg" in
    up)
      ACTION="up"
      ;;
    down)
      ACTION="down"
      ;;
    --with-local-test-setup)
      WITH_LOCAL_TEST_SETUP=true
      ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

run_compose() {
  local dir="$1"; shift
  if [ "$ACTION" = "up" ]; then
    (cd "$dir" && docker compose up -d --build "$@")
  else
    (cd "$dir" && docker compose down)
  fi
}

run_compose "$FALCON_DIR"
if [ "$WITH_LOCAL_TEST_SETUP" = true ]; then
  if [ "$ACTION" = "up" ]; then
    # Bring up the MCP servers first so register-falcon.sh can sync their
    # tools (and so story-backend, started last, picks up MCP_AGENT_KEY).
    run_compose "$TEST_SETUP_DIR" db-mcp-server email-mcp-server mailhog
    "$TEST_SETUP_DIR/register-falcon.sh"
    run_compose "$TEST_SETUP_DIR"
  else
    run_compose "$TEST_SETUP_DIR"
  fi
fi
