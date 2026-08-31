#!/usr/bin/env python3
"""Dump MCP tool JSON schemas. Never places orders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings

OUT = ROOT / "docs" / "mcp-schemas"
WANTED = (
    "place_option_order",
    "get_option_chain",
    "get_option_snapshot",
    "get_account_info",
    "get_clock",
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    if not s.resolved_api_key():
        print("ALPACA_API_KEY missing", file=sys.stderr)
        return 2
    if not s.alpaca_secret_key:
        print("ALPACA_SECRET_KEY missing", file=sys.stderr)
        return 2
    from mcp_integration.client import list_tools_sync

    tools = list_tools_sync()
    index = {t["name"]: t for t in tools}
    (OUT / "all_tools.json").write_text(json.dumps(sorted(index), indent=2) + "\n")
    for name in WANTED:
        if name in index:
            (OUT / f"{name}.json").write_text(json.dumps(index[name], indent=2) + "\n")
    print("dumped", len(index), "tools to", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
