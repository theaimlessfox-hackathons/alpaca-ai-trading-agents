# MCP schemas

Live dump via `tools/schema_introspect.py` against official `uvx alpaca-mcp-server` (72 tools).

`place_option_order` multi-leg (from live tool description):

- required: `qty`
- `order_class`: `mleg` (inferred if `legs` present)
- each leg: **`symbol`** (OCC) + **`ratio_qty`** (string); optional `side`, `position_intent`
- `client_order_id` recommended for idempotency
- `limit_price` is net debit (positive) / credit (negative) for multi-leg
- `time_in_force`: day only

Do not commit `.env`. Dumps contain no API keys. Never call `place_option_order` from research/account modules.

## Confirmed live (Aug 30, sandbox account PA3KII0I2OJ1) -- corrects assumptions baked into earlier code

- **Options level**: `options_approved_level` / `options_trading_level` are both `3` on this account already. The
  "verify, don't assume" risk item is resolved for the sandbox account; still confirm on the separate competition
  account once it exists.
- **Every tool response is wrapped**: `{"_alpaca_mcp_security": {trust, tool_name, risk, instructions}, "data": {...}}`.
  Not documented in the dumped input schemas (those only cover requests). `tools/research_tools.unwrap()` strips
  this automatically now -- downstream code should never see the envelope.
- **No greeks, no implied volatility, from either `get_option_chain` or `get_option_snapshot` on this account**,
  despite both tools' descriptions claiming they're included. Requesting `feed=opra` explicitly 403s with
  `"OPRA agreement is not signed"`; the default/`indicative` feed this account falls back to carries `latestQuote`
  (and sometimes `dailyBar`/`latestTrade`) but never `greeks` or `impliedVolatility`. `strategy/chain.py` now derives
  delta and IV from the mid quote via Black-Scholes inversion (`strategy/blackscholes.py`) whenever they're absent
  and a spot price is available -- this is the normal path on this account, not a rare fallback.
- **Contract symbols are not OCC-space-padded**: a real chain entry key looks like `SPY260908C00510000` (18 chars
  for a 3-letter root), not the 6-char-padded `SPY   260908C00510000` (21 chars) the raw OCC/OPRA standard uses.
  `strategy/structures.py:occ_symbol()` was originally padding and has been corrected; unpadded is very likely what
  `place_option_order` expects too, since it's what the rest of the API surface actually returns, but this hasn't
  been confirmed with a real order submission yet.
- **`get_stock_bars` takes `symbols` (plural, comma-separated string) and `days` (int lookback)**, not `symbol` +
  `days` as the code originally assumed -- confirmed via a live "invalid arguments" error. `tools/research_tools.py`
  is fixed.
- Market was closed at check time (`is_open: false`, `next_open: 2026-08-31T09:30:00-04:00`), consistent with the
  plan's Sunday-evening timing.
