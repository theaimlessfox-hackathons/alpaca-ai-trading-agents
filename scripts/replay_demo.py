#!/usr/bin/env python3
"""Offline replay: load fixture, print the 90s story. No orders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", default="fixtures/replay_spy.json")
    args = p.parse_args()
    data = json.loads(Path(args.fixture).read_text())
    print("ThetaGate replay", data["symbol"])
    for c in data["cycles"]:
        print("-", c["verdict"], c["reason"], "|", c.get("thesis", ""))
        if c.get("critic"):
            print("  challenge:", c["critic"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
