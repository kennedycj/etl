#!/usr/bin/env bash
# Run one OpenClaw agent turn that should invoke the exec/bash tool to run a script.
#
# Prerequisites:
#   - Docker Desktop running
#   - Gateway up: docker compose -f docker-compose.openclaw.yml up -d
#   - Repo mounted at /workspace/etl in the gateway (see docker-compose.openclaw.yml)
#
# Runs the bundled `openclaw` CLI *inside* the gateway container (--container etl-openclaw-gateway)
# so paths match /home/node/.openclaw/workspace and gateway auth stays consistent.
#
# Usage:
#   ./scripts/openclaw_agent_exec_test.sh
#   ./scripts/openclaw_agent_exec_test.sh --json

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

chmod +x scripts/openclaw_exec_probe.sh || true

compose() {
  if docker compose version >/dev/null 2>&1; then docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then docker-compose "$@"
  else
    echo "Docker Compose not found." >&2
    exit 1
  fi
}

compose -f docker-compose.openclaw.yml up -d --build openclaw-gateway

export OPENCLAW_CONTAINER="${OPENCLAW_CONTAINER:-etl-openclaw-gateway}"

PROBE='sh /workspace/etl/scripts/openclaw_exec_probe.sh'

MSG="$(cat <<EOF
Use your shell/exec tool exactly once (do not pretend you ran it). Execute this command and nothing else:

${PROBE}

Reply with ONLY the single line printed to stdout (no markdown, no quotes). If tools are unavailable, say EXEC_UNAVAILABLE.
EOF
)"

JSON_FLAG=()
if [[ "${1:-}" == "--json" ]]; then
  JSON_FLAG=(--json)
fi

echo "Running exec probe via OpenClaw agent (container: ${OPENCLAW_CONTAINER})..." >&2

openclaw --container "${OPENCLAW_CONTAINER}" agent --agent main -m "${MSG}" "${JSON_FLAG[@]}"
