"""Opt-in status line: one English line showing Maestro is on, model, cost and agent counts."""

import json
import os
import sys
from pathlib import Path

import hooklib as h


def build(payload):
    parts = ["Maestro ✓"]
    model = (payload.get("model") or {}).get("display_name")
    if model:
        parts.append(str(model))
    cost = (payload.get("cost") or {}).get("total_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        parts.append(f"${cost:.2f}")
    ws = payload.get("workspace") or {}
    base = ws.get("project_dir") or payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    if base:
        lines = h.ledger_lines(h.data_dir(Path(base)))
        if lines is not None:
            rows = h.ledger_rows(lines)
            parts.append(f"agents {len(rows)} ({h.count_unrated(lines)} unrated)")
    return " | ".join(parts)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        payload = json.loads(sys.stdin.read() or "{}")
        line = build(payload if isinstance(payload, dict) else {})
    except Exception:  # noqa: BLE001
        line = "Maestro"
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
