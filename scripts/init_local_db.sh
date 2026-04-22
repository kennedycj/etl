#!/usr/bin/env bash
# Start Docker Postgres and create application tables (idempotent create).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DATABASE_URL="${DATABASE_URL:-postgresql://finance_user:finance_password@127.0.0.1:5432/finance}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH. Install Docker Desktop: https://docs.docker.com/desktop/"
  exit 1
fi

# Compose v2: "docker compose" (plugin). Legacy: "docker-compose" standalone.
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "Docker Compose not found. Install Compose v2 (Docker Desktop includes it) or: brew install docker-compose"
    echo "Check: docker compose version   OR   docker-compose --version"
    exit 1
  fi
}

compose up -d

echo "Waiting for Postgres..."
for _ in $(seq 1 60); do
  if compose exec -T postgres pg_isready -U finance_user -d finance >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

PY="${PYTHON:-python3}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
fi

echo "Creating tables with: $PY create_tables.py ..."
exec "$PY" create_tables.py "$DATABASE_URL"
