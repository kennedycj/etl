"""Shared helpers for MCP servers (database URL, snapshot payload)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from finance_app.agents.analyzer import FinancialAnalyzer
from finance_app.database.connection import create_database_engine, create_session_factory


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    if Path("/.dockerenv").exists():
        return (
            "postgresql://finance_user:finance_password@"
            "host.docker.internal:5432/finance"
        )
    return "postgresql://finance_user:finance_password@127.0.0.1:5432/finance"


def snapshot_payload() -> dict:
    engine = create_database_engine(database_url())
    SessionFactory = create_session_factory(engine)
    session = SessionFactory()
    try:
        analyzer = FinancialAnalyzer(session)
        return {
            "ok": True,
            "account_summary": analyzer.get_account_summary(),
            "net_worth": analyzer.get_net_worth(),
            "unreconciled": analyzer.get_unreconciled_transactions(),
        }
    finally:
        session.close()


def snapshot_json() -> str:
    return json.dumps(snapshot_payload(), indent=2)
