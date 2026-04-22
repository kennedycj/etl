#!/usr/bin/env python3
"""MCP server (stdio) exposing finance snapshot tools backed by Postgres.

Runs as a subprocess of OpenClaw (`mcp.servers`) or other MCP hosts.

Repo root on PYTHONPATH via sys.path below; DATABASE_URL inherited from the host /
gateway unless unset (then uses local defaults mirroring scripts/finance_overview_gateway.sh).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from mcp.server.fastmcp import FastMCP

from finance_app.agents.analyzer import FinancialAnalyzer
from finance_app.database.connection import create_database_engine, create_session_factory


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    # Matches docker-compose.openclaw gateway defaults when /.dockerenv is present.
    if Path("/.dockerenv").exists():
        return (
            "postgresql://finance_user:finance_password@"
            "host.docker.internal:5432/finance"
        )
    return (
        "postgresql://finance_user:finance_password@"
        "127.0.0.1:5432/finance"
    )


def _snapshot_payload() -> dict:
    engine = create_database_engine(_database_url())
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()
    try:
        analyzer = FinancialAnalyzer(session)
        summary = analyzer.get_account_summary()
        net = analyzer.get_net_worth()
        unreconciled = analyzer.get_unreconciled_transactions()
        return {
            "ok": True,
            "account_summary": summary,
            "net_worth": net,
            "unreconciled": unreconciled,
        }
    finally:
        session.close()


mcp = FastMCP("etl-finance")


@mcp.tool()
def get_finance_snapshot() -> str:
    """Live finance overview from Postgres: accounts, balances, net worth, unreconciled counts. Returns JSON."""
    payload = _snapshot_payload()
    return json.dumps(payload, indent=2)


@mcp.tool()
def finance_overview_smoke() -> str:
    """Smoke test: confirms at least one account exists and net_worth is computed. Returns short text."""
    payload = _snapshot_payload()
    summary = payload["account_summary"]
    net = payload["net_worth"]
    if summary.get("total_accounts", 0) < 1:
        return "smoke failed: no accounts (seed with scripts/seed_sandbox.py on the host)."
    if "net_worth" not in net:
        return "smoke failed: missing net_worth in analyzer output."
    return "smoke OK"


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
