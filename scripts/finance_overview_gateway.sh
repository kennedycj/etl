#!/usr/bin/env sh
# Run finance_overview.py inside the OpenClaw gateway container.
#
# OpenClaw's exec tool often does not inherit the gateway process environment, so
# DATABASE_URL may be empty. This wrapper applies the same default as
# docker-compose.openclaw.yml when DATABASE_URL is unset.
#
# Usage (inside gateway):
#   sh /workspace/etl/scripts/finance_overview_gateway.sh
#   sh /workspace/etl/scripts/finance_overview_gateway.sh   # with args passed through

export DATABASE_URL="${DATABASE_URL:-postgresql://finance_user:finance_password@host.docker.internal:5432/finance}"
exec python3 "$(dirname "$0")/finance_overview.py" "$@"
