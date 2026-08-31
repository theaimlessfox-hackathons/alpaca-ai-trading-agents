from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def is_market_open(now: datetime | None = None) -> bool:
    ts = now.astimezone(ET) if now else datetime.now(ET)
    if ts.weekday() >= 5:
        return False
    minutes = ts.hour * 60 + ts.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)
