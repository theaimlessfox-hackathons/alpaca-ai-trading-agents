from config.settings import get_settings


def iter_universe(settings=None) -> list[str]:
    s = settings or get_settings()
    if s.universe_mode == "pinned":
        return [str(sym).upper() for sym in s.universe]
    from strategy.universe import discover_universe

    return discover_universe(limit=s.universe_size)


def filter_symbol(symbol: str, settings=None) -> str | None:
    name = (symbol or "").strip().upper()
    allowed = {str(sym).upper() for sym in iter_universe(settings)}
    return name if name in allowed else None
