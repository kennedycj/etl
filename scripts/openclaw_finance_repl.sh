#!/usr/bin/env bash
# Interactive multi-turn OpenClaw agent (same session) — try finance questions and watch exec/tool use.
#
# Prerequisites:
#   - Postgres running on the host with port 5432 published (see docker-compose.yml).
#   - Gateway image includes Python deps (Dockerfile.openclaw-gateway + compose build).
#   - Optional: seed dummy data on the HOST before chatting:
#       set -a && source .env.local && set +a && python scripts/seed_sandbox.py
#
# Usage:
#   ./scripts/openclaw_finance_repl.sh
#   SESSION_ID=my-run ./scripts/openclaw_finance_repl.sh   # resume a session
#
# Interaction:
#   - Type natural-language prompts; use "exit" or "quit" to leave.
#   - Each reply shows assistant text; tool routing is printed to stderr when present
#     (including toolSummary, e.g. exec).
#   - For full JSON of the last turn: /tmp/openclaw-last.json (tee from this script).
#
# Alternative: Open the Control UI in a browser at http://127.0.0.1:18789/ (same gateway).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

compose() {
  if docker compose version >/dev/null 2>&1; then docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then docker-compose "$@"
  else
    echo "Docker Compose not found." >&2
    exit 1
  fi
}

mkdir -p .openclaw_runtime/workspace

# FINANCE_TOOLS.md for the agent is bind-mounted from ./openclaw_workspace/FINANCE_TOOLS.md (see docker-compose.openclaw.yml).

compose -f docker-compose.openclaw.yml up -d --build openclaw-gateway

export OPENCLAW_CONTAINER="${OPENCLAW_CONTAINER:-etl-openclaw-gateway}"

SESSION_ID="${SESSION_ID:-finance-demo-${RANDOM}}"
LAST_JSON="${LAST_JSON:-/tmp/openclaw-last.json}"

echo "══ OpenClaw finance REPL ══" >&2
echo "Session id: ${SESSION_ID}  (re-use with: export SESSION_ID=${SESSION_ID})" >&2
echo "Last raw JSON: ${LAST_JSON}" >&2
echo "Control UI:   http://127.0.0.1:18789/" >&2
echo >&2

while IFS= read -rp "> " line; do
  [[ -z "${line// }" ]] && continue
  if [[ "$line" == "exit" || "$line" == "quit" ]]; then
    break
  fi

  openclaw --container "${OPENCLAW_CONTAINER}" agent \
    --agent main \
    --session-id "${SESSION_ID}" \
    -m "${line}" \
    --json \
    | tee "${LAST_JSON}" \
    | python3 "${ROOT}/scripts/openclaw_print_turn.py"

done

echo "Bye." >&2
