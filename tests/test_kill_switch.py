from datetime import datetime, timedelta
from pathlib import Path

from config.settings import Settings
from risk.kill_switch import cooldown_active, is_halted, is_killed, set_kill_switch


def test_flag(tmp_path: Path):
    flag = tmp_path / "KILL"
    assert is_killed(flag) is False
    set_kill_switch(True, flag)
    assert is_killed(flag) is True
    set_kill_switch(False, flag)
    assert is_killed(flag) is False


def test_halts():
    s = Settings()
    halted, why = is_halted(96_900, 100_000, 100_000, s)
    assert halted and why == "daily_halt"
    halted, why = is_halted(91_900, 92_000, 100_000, s)
    assert halted and why == "total_halt"
    halted, why = is_halted(99_000, 100_000, 100_000, s)
    assert not halted


def test_cooldown():
    s = Settings()
    now = datetime(2026, 8, 31, 12, 0, 0)
    last = now - timedelta(minutes=s.cooldown_minutes - 1)
    assert cooldown_active(last, now, s) is True
    last = now - timedelta(minutes=s.cooldown_minutes, seconds=1)
    assert cooldown_active(last, now, s) is False
    assert cooldown_active(None, now, s) is False
