from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pin-list only. Discover mode ignores this and reads Alpaca market data.
PINNED_UNIVERSE = ("SPY", "QQQ", "IWM")
LOCKED_UNIVERSE = PINNED_UNIVERSE  # back-compat alias for tests/docs


def parse_compete_after(raw: str) -> datetime | None:
    """ISO date or datetime. Date-only is treated as 00:00 UTC that day.

    Returns None when the string is empty or unparseable — callers fail closed.
    """
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alpaca_api_key: str = ""
    alpaca_key: str = ""  # some dashboards export ALPACA_KEY
    alpaca_secret_key: str = ""
    alpaca_paper_trade: bool = True
    alpaca_account_role: str = "sandbox"
    expected_account_id: str = ""
    compete_enabled: bool = False
    compete_after: str = ""

    alpaca_competition_api_key: str = ""
    alpaca_competition_secret_key: str = ""
    alpaca_competition_account_id: str = ""

    featherless_api_key: str = ""
    featherless_base_url: str = "https://api.featherless.ai/v1"
    featherless_url: str = ""  # some .env files export FEATHERLESS_URL
    featherless_model: str = ""
    use_anthropic_fallback: bool = False
    anthropic_api_key: str = ""

    xai_api_key: str = ""
    xai_model: str = ""
    xai_base_url: str = "https://api.x.ai/v1"
    xai_fallback: bool = False

    fallback_mleg: bool = False
    entry_timeout_minutes: int = 30

    universe_mode: str = "discover"  # discover | pinned
    universe_size: int = 6
    universe: tuple[str, ...] = PINNED_UNIVERSE
    dte_min: int = 7
    dte_max: int = 21
    short_delta_min: float = 0.20
    short_delta_max: float = 0.30
    long_delta_min: float = 0.10
    long_delta_max: float = 0.15
    max_loss_pct: float = 0.02
    max_open_structures: int = 3
    max_per_underlying: int = 2
    daily_halt_pct: float = 0.03
    total_halt_pct: float = 0.08
    expiry_sweep_days: int = 2
    cooldown_minutes: int = 75
    cycle_minutes: int = 25
    snapshot_minutes: int = 5
    rv_lookback_days: int = 20
    iv_rv_rich_min: float = 1.2
    iv_sane_min: float = 0.05
    iv_sane_max: float = 2.5
    bid_ask_max_frac: float = 0.20
    take_profit_frac: float = 0.50
    stop_mult: float = 2.0
    risk_free_rate: float = 0.04

    @property
    def paper_trade(self) -> bool:
        return self.alpaca_paper_trade

    def resolved_api_key(self) -> str:
        return self.alpaca_api_key or self.alpaca_key

    def resolved_featherless_base_url(self) -> str:
        return self.featherless_base_url or self.featherless_url or "https://api.featherless.ai/v1"

    def competing(self) -> bool:
        return self.alpaca_account_role == "competition" or self.compete_enabled

    def execution_credentials(self) -> tuple[str, str]:
        """Keys the broker and MCP client must use.

        Competition mode never falls back to the generic sandbox pair — missing
        competition credentials is a hard failure, not a silent swap.
        """
        if self.competing():
            if not self.alpaca_competition_api_key or not self.alpaca_competition_secret_key:
                raise RuntimeError("competition credentials required")
            return self.alpaca_competition_api_key, self.alpaca_competition_secret_key
        return self.resolved_api_key(), self.alpaca_secret_key

    def compete_window_open(self, now: datetime | None = None) -> bool:
        """True when live competition is allowed to submit.

        Empty compete_after means no time gate. An unparseable value fails closed.
        """
        raw = (self.compete_after or "").strip()
        if not raw:
            return True
        parsed = parse_compete_after(raw)
        if parsed is None:
            return False
        ts = now or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts >= parsed

    @field_validator("alpaca_paper_trade")
    @classmethod
    def paper_only(cls, v: bool) -> bool:
        if v is False:
            raise ValueError("live trading is not allowed")
        return True

    @field_validator("universe_mode")
    @classmethod
    def mode_ok(cls, v: str) -> str:
        mode = (v or "discover").strip().lower()
        if mode not in {"discover", "pinned"}:
            raise ValueError("UNIVERSE_MODE must be discover or pinned")
        return mode

    @field_validator("universe", mode="before")
    @classmethod
    def parse_universe(cls, v: object) -> tuple[str, ...]:
        if v is None or v == "":
            return PINNED_UNIVERSE
        if isinstance(v, str):
            parts = tuple(s.strip().upper() for s in v.split(",") if s.strip())
            return parts or PINNED_UNIVERSE
        return tuple(str(x).strip().upper() for x in v)  # type: ignore[arg-type]

    @field_validator("alpaca_account_role")
    @classmethod
    def role_ok(cls, v: str) -> str:
        if v not in {"sandbox", "competition"}:
            raise ValueError("ALPACA_ACCOUNT_ROLE must be sandbox or competition")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
