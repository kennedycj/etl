"""Run repository root *.py scripts and capture stdout (for MCP tools)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_repo_script(script_relative: str, *, timeout: int = 300) -> str:
    script = REPO_ROOT / script_relative
    if not script.is_file():
        return f"Missing script: {script}"
    env = os.environ.copy()
    p = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        env=env,
    )
    out = (p.stdout or "") + ((p.stderr or "") if p.stderr else "")
    if p.returncode != 0:
        return f"[exit {p.returncode}]\n{out}"[:48000]
    return out[:50000]
