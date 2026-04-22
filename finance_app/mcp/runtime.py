"""Shared helpers for MCP servers (database URL, snapshot payload)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from finance_app.agents.analyzer import FinancialAnalyzer
from finance_app.database.connection import create_database_engine, create_session_factory


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # In Docker, 127.0.0.1/localhost points at the container, not the host Postgres.
        # If the operator accidentally passed a host-style URL into the gateway env,
        # rewrite it to host.docker.internal.
        if Path("/.dockerenv").exists():
            try:
                p = urlparse(url)
                if p.hostname in {"127.0.0.1", "localhost"}:
                    netloc = p.netloc.replace(p.hostname, "host.docker.internal")
                    return urlunparse(p._replace(netloc=netloc))
            except Exception:
                pass
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
