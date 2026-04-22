#!/usr/bin/env bash
# Register the finance MCP server with OpenClaw (stdio transport).
#
# The gateway runs MCP children **inside the same container** as the gateway when
# you use Docker. Paths in config must therefore be **container paths**
# (/workspace/etl), not your Mac path.
#
# Prerequisites:
#   - requirements.txt includes mcp[cli]; gateway image rebuilt after changes.
#
# Usage (from repo root on the host):
#   export OPENCLAW_STATE_DIR="$PWD/.openclaw_runtime/config"
#   export OPENCLAW_CONFIG_PATH="$PWD/.openclaw_runtime/config/openclaw.json"
#   ./scripts/register_openclaw_mcp_finance.sh
#
# Optional: run openclaw inside the gateway where paths match:
#   docker exec etl-openclaw-gateway openclaw mcp set etl-finance '<json>'
#
# Verify:
#   openclaw mcp show etl-finance --json

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Paths seen by the OpenClaw **gateway process** (Docker mount in docker-compose.openclaw.yml).
DOCKER_REPO="${DOCKER_REPO:-/workspace/etl}"

JSON="$(python3 -c "
import json
cfg = {
    \"command\": \"python3\",
    \"args\": [\"${DOCKER_REPO}/scripts/mcp_finance_server.py\"],
    \"cwd\": \"${DOCKER_REPO}\",
}
print(json.dumps(cfg))
")"

openclaw() {
  command openclaw "$@"
}

if [[ -n "${OPENCLAW_CONTAINER:-}" ]]; then
  openclaw() {
    docker exec "${OPENCLAW_CONTAINER}" openclaw "$@"
  }
fi

echo "Registering MCP server \"etl-finance\" (stdio) → ${DOCKER_REPO}/scripts/mcp_finance_server.py"
openclaw mcp set etl-finance "$JSON"

echo "Done. Verify (set OPENCLAW_CONFIG_PATH to this project if you are not using only Docker):"
echo "  openclaw mcp show etl-finance --json"
echo "  # or: docker exec etl-openclaw-gateway openclaw mcp show etl-finance --json"
echo "Restart the etl-openclaw-gateway container if tools do not load."
