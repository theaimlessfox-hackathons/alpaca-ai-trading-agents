"""JSONL decision log. No secrets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("logs/decisions.jsonl")


def log_event(kind: str, **fields) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
    for k in list(row):
        if "key" in k.lower() or "secret" in k.lower():
            row.pop(k)
    with LOG.open("a") as f:
        f.write(json.dumps(row) + "\n")
