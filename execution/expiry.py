"""Wave-2 backup: close if DTE <= expiry_sweep_days. Happy path does not use this."""

from __future__ import annotations

from config.settings import get_settings


def should_sweep(dte: int, settings=None) -> bool:
    s = settings or get_settings()
    return dte <= s.expiry_sweep_days
