from config.settings import get_settings


def iter_universe(settings=None) -> list[str]:
    s = settings or get_settings()
    return list(s.universe)


def filter_symbol(symbol: str, settings=None) -> str | None:
    allowed = set(iter_universe(settings))
    return symbol if symbol in allowed else None
