#!/usr/bin/env python3
"""Read one OpenClaw agent --json blob from stdin; print assistant text + stderr metadata."""
from __future__ import annotations

import json
import sys


def main() -> None:
    j = json.load(sys.stdin)
    r = j.get("result") or {}
    text = (r.get("payloads") or [{}])[0].get("text", "")
    meta = r.get("meta") or {}
    print(text)
    ts = meta.get("toolSummary")
    if ts:
        print(f"[toolSummary] {ts}", file=sys.stderr)
    am = meta.get("agentMeta") or {}
    prov, model = am.get("provider"), am.get("model")
    if prov or model:
        print(f"[model] {prov}/{model}", file=sys.stderr)


if __name__ == "__main__":
    main()
