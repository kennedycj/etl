#!/usr/bin/env python3
"""Stdio entrypoint for the etl-finance MCP server (OpenClaw, Cursor, etc.)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from finance_app.mcp.server import main

if __name__ == "__main__":
    main()
