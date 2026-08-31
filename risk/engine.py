from __future__ import annotations

from dataclasses import dataclass, field

from config.settings import get_settings
from risk.types import Approve, Veto


@dataclass
class Leg:
    side: str  # short | long
    right: str  # put | call
    strike: float
    delta: float
    bid: float
    ask: float
    iv: float
    occ_symbol: str | None = None


@dataclass
class ProposalView:
    symbol: str
    structure: str
    dte: int
    legs: list[Leg]
    est_max_loss: float = 0.0
    qty: int = 1
    expiration: str | None = None
    # SPY/QQQ/IWM are index ETFs -- they have no earnings dates, so an "earnings"
    # veto here would structurally never fire. This flags ex-dividend or a macro
    # release (FOMC/CPI/jobs) landing inside the spread's life instead.
    event_in_life: bool = False


@dataclass
class PortfolioView:
    nav: float
    open_count: int = 0
    per_underlying: dict[str, int] = field(default_factory=dict)
    overlapping_short: bool = False
    daily_halt: bool = False
    total_halt: bool = False
    killed: bool = False
    cooldown: bool = False


def credit(legs: list[Leg]) -> float:
    c = 0.0
    for leg in legs:
        mid = (leg.bid + leg.ask) / 2
        c += mid if leg.side == "short" else -mid
    return c


def width(legs: list[Leg]) -> float:
    strikes = [lg.strike for lg in legs]
    return abs(max(strikes) - min(strikes))


def computed_max_loss(proposal: ProposalView) -> float:
    # Vertical credit: (width - credit) * 100 * qty
    return max(0.0, (width(proposal.legs) - credit(proposal.legs)) * 100 * proposal.qty)


def validate(proposal: ProposalView, book: PortfolioView, settings=None) -> Approve | Veto:
    s = settings or get_settings()
    if proposal.symbol not in s.universe:
        return Veto("universe")
    if proposal.structure != "credit_spread":
        return Veto("structure")
    if not (s.dte_min <= proposal.dte <= s.dte_max):
        return Veto("dte")
    if len(proposal.legs) != 2:
        return Veto("legs")
    shorts = [lg for lg in proposal.legs if lg.side == "short"]
    longs = [lg for lg in proposal.legs if lg.side == "long"]
    if len(shorts) != 1 or len(longs) != 1:
        return Veto("legs")
    sh, lo = shorts[0], longs[0]
    if sh.right != lo.right or sh.right not in {"put", "call"}:
        return Veto("rights")
    if sh.right == "put" and not (lo.strike < sh.strike):
        return Veto("geometry")
    if sh.right == "call" and not (lo.strike > sh.strike):
        return Veto("geometry")
    if proposal.qty <= 0:
        return Veto("qty")
    cr = credit(proposal.legs)
    w = width(proposal.legs)
    if cr <= 0:
        return Veto("credit")
    if w <= 0 or cr >= w:
        return Veto("credit")
    if not (s.short_delta_min <= abs(sh.delta) <= s.short_delta_max):
        return Veto("short_delta")
    if not (s.long_delta_min <= abs(lo.delta) <= s.long_delta_max):
        return Veto("long_delta")
    mx = computed_max_loss(proposal)
    if book.nav <= 0 or mx > s.max_loss_pct * book.nav:
        return Veto("max_loss")
    if book.open_count >= s.max_open_structures:
        return Veto("open_count")
    if book.per_underlying.get(proposal.symbol, 0) >= s.max_per_underlying:
        return Veto("per_underlying")
    if book.overlapping_short:
        return Veto("overlap")
    if sh.bid <= 0 or sh.ask <= 0 or sh.ask < sh.bid:
        return Veto("bid_ask")
    mid = (sh.bid + sh.ask) / 2
    if mid > 0 and (sh.ask - sh.bid) / mid > s.bid_ask_max_frac:
        return Veto("bid_ask")
    if lo.bid <= 0 or lo.ask <= 0 or lo.ask < lo.bid:
        return Veto("long_quote")
    mid_lo = (lo.bid + lo.ask) / 2
    if mid_lo > 0 and (lo.ask - lo.bid) / mid_lo > s.bid_ask_max_frac:
        return Veto("bid_ask")
    if not (s.iv_sane_min <= sh.iv <= s.iv_sane_max):
        return Veto("iv")
    if not (s.iv_sane_min <= lo.iv <= s.iv_sane_max):
        return Veto("iv")
    if proposal.event_in_life:
        return Veto("event_risk")
    if book.daily_halt:
        return Veto("daily_halt")
    if book.total_halt:
        return Veto("total_halt")
    if book.killed:
        return Veto("kill_switch")
    if book.cooldown:
        return Veto("cooldown")
    return Approve(max_loss=mx)
