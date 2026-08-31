from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from config.settings import get_settings

FLAG = Path("logs/KILL")


def set_kill_switch(on: bool, path: Path = FLAG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if on:
        path.write_text("1\n")
    elif path.exists():
        path.unlink()


def is_killed(path: Path = FLAG) -> bool:
    return path.exists()


def is_halted(equity: float, sod: float, start: float, settings=None) -> tuple[bool, str | None]:
    s = settings or get_settings()
    if sod > 0 and (sod - equity) / sod >= s.daily_halt_pct:
        return True, "daily_halt"
    if start > 0 and (start - equity) / start >= s.total_halt_pct:
        return True, "total_halt"
    return False, None


def cooldown_active(last_ts: datetime | None, now: datetime, settings=None) -> bool:
    if last_ts is None:
        return False
    s = settings or get_settings()
    return now < last_ts + timedelta(minutes=s.cooldown_minutes)
