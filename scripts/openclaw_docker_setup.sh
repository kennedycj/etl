#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Docker Compose not found. Install Docker Desktop (includes Compose v2) or: brew install docker-compose" >&2
    exit 1
  fi
}

OPENCLAW_IMAGE="${OPENCLAW_IMAGE:-ghcr.io/openclaw/openclaw:latest}"
export OPENCLAW_IMAGE

mkdir -p .openclaw_runtime/config .openclaw_runtime/workspace

echo "Using OpenClaw image: $OPENCLAW_IMAGE"

if [ ! -f ".openclaw_runtime/config/openclaw.json" ]; then
  echo "No local OpenClaw config found. Running onboarding (interactive)..."
  compose -f docker-compose.openclaw.yml run --rm --no-deps --entrypoint node openclaw-gateway \
    dist/index.js onboard --mode local --no-install-daemon

  echo "Setting gateway bind to LAN for host access..."
  compose -f docker-compose.openclaw.yml run --rm --no-deps --entrypoint node openclaw-gateway \
    dist/index.js config set --batch-json '[{"path":"gateway.mode","value":"local"},{"path":"gateway.bind","value":"lan"},{"path":"gateway.controlUi.allowedOrigins","value":["http://localhost:18789","http://127.0.0.1:18789"]}]'
fi

echo "Starting gateway (builds etl-openclaw-gateway:local with Python + etl requirements)..."
compose -f docker-compose.openclaw.yml up -d --build openclaw-gateway

echo "Waiting for healthz..."
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:18789/healthz >/dev/null 2>&1; then
    echo "OK"
    exit 0
  fi
  sleep 1
done

echo "Gateway did not become healthy in time." >&2
echo "Try: docker logs etl-openclaw-gateway" >&2
exit 1

