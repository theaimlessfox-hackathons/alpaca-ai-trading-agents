# ThetaGate — one page

ThetaGate is an autonomous paper desk that sells defined-risk **credit spreads** on SPY, QQQ, and IWM when ATM implied vol is rich versus 20-day realized vol. It stands down in cheap vol or a simple breakout.

**AI logic.** A Featherless model proposes a two-leg spread from prefetched chain slices. JSON must parse as `TradeProposal` (≤3 retries) or there is no trade. A short critic can challenge the idea; it cannot spend. The model never sees order tools.

**Risk gates.** Python recomputes max loss, DTE, deltas, universe, overlap, bid-ask, IV band, daily −3% and total −8% halts, cooldown, and a file kill switch. Invalid proposals are stored as vetoes. (There's a structural slot for a macro/ex-dividend event-risk veto, not an earnings gate — SPY/QQQ/IWM are index ETFs with no earnings dates — but nothing populates it yet, so it isn't an active line item.)

**Alpaca infra.** Trading API via official MCP (`place_option_order` multi-leg, `qty` + OCC `symbol`/`ratio_qty`). CLI is one read (`alpaca account`) for the stack requirement. Paper only. A dedicated $100k competition account is used for judging; sandbox is for breakage.

**Lifecycle.** Orders and structures have separate statuses. Canceling a partial entry leaves an OPEN structure. Closes are atomic or fail closed.
