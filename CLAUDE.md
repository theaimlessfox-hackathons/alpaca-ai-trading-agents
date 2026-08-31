# ThetaGate

Autonomous paper desk: defined-risk **credit spreads** on SPY/QQQ/IWM when ATM IV / 20-day RV is rich.

## Safety

- The LLM never receives `place_option_order` or any order tool.
- `execution/` is the only place that may submit.
- Risk engine + kill switch + account guard re-check immediately before submit.
- Invalid model JSON: parse-and-retry ≤3, then **no trade**.
- Paper only. `ALPACA_PAPER_TRADE` must be true. No live path.
- Close is **one atomic multi-leg order** or fail closed. Never leg out.

## Two status machines (`config/states.py`)

- **OrderStatus:** INTENT → SUBMITTING → WORKING → PARTIALLY_FILLED → FILLED | CANCELED | REJECTED | EXPIRED | NEEDS_REVIEW
- **StructureStatus:** PENDING_ENTRY → OPEN → CLOSING → CLOSED | NEEDS_REVIEW
- Canceling a partial entry leaves the structure **OPEN** for filled qty.

## Accounts

- Sandbox: break things.
- Competition: brand-new paper account, **$100,000**, unused until `COMPETE_ENABLED=true` and `EXPECTED_ACCOUNT_ID` matches.
- Public event page requires a dedicated new paper account + account ID on the submission.

## Strategy (locked)

- Universe: SPY, QQQ, IWM
- Structure: put/call credit spread only (no iron condor)
- DTE 7–21; short delta 0.20–0.30; long 0.10–0.15
- Regime: ATM IV / 20d RV — not IV rank
- Risk: ≤2% NAV/structure; max 3 open; daily −3%; total −8%
- Exits: 40–60% of credit, loss multiple, regime flip, halt flatten

## Submission

Submission facts live in `docs/SUBMISSION_FIELDS.md` (demo-submission/001). Deadline and video format stay **provisional** pending that issue / the logged-in form.

- Window 28 Aug–4 Sep 2026. Public schedule: **4 Sep 9:00 PM British Summer Time = 20:00 UTC**. (Not Bangladesh Standard Time — that's UTC+6 and would be 15:00 UTC; the 20:00 UTC figure only matches BST.) Submit earlier.
- Required on the event page: options, MCP or CLI, **new $100k paper account**, **account ID**, one-pager.
- Video: generic lablab is **MP4 ≤5 min upload**. Logged-in form not opened — recheck widget.

## Alpaca MCP chat (demo)

Official server: account, positions, orders, market data only. It cannot halt ThetaGate or read our SQLite log.

## MCP `place_option_order` (live dump, 72 tools)

See `docs/mcp-schemas/place_option_order.json`. Multi-leg: `qty` required; `legs[]` each need OCC `symbol` + `ratio_qty`; optional `side` / `position_intent`; `order_class=mleg` inferred; `limit_price` is net debit (+) / credit (−); `client_order_id` for idempotency. Never give this tool to the LLM.

## Wave 2 (not Sunday)

Critic LLM, MCP auto-restart supervisor, extra CLI, run-cycle-now, social.

## Confirmed live (Aug 30, sandbox account PA3KII0I2OJ1) -- corrects earlier assumptions

Full detail in `docs/mcp-schemas/SOURCE.md`. Headlines, because these change how the
data path is written, not just what it returns:

- **Options level 3 already active** on the sandbox account; $100k confirmed.
- **Every MCP tool response is wrapped**: `{"_alpaca_mcp_security": {...}, "data": {...}}`.
  `tools/research_tools.unwrap()` strips this centrally now -- nothing downstream should
  ever see the envelope.
- **This account's feed returns no greeks and no IV most of the time.** `feed=opra` 403s
  ("OPRA agreement is not signed"); the indicative fallback only sometimes carries
  `greeks`/`impliedVolatility` (liquid/recently-traded contracts) and often just has
  `latestQuote`. `strategy/chain.py` derives delta/IV via Black-Scholes inversion
  (`strategy/blackscholes.py`) from the mid quote whenever the broker didn't supply them.
  This is the normal path, not a rare fallback -- treat it as load-bearing.
- **Option snapshots carry no `strike_price`/`expiration_date`/`type` fields at all** --
  only the contract symbol encodes them (e.g. `SPY260908C00726000`). `strategy/chain.py`
  derives all three from the OCC symbol; do not assume separate fields exist.
- **`occ_symbol()` must not space-pad the root.** Real contract symbols are unpadded
  (`SPY260908C00510000`, 18 chars for a 3-letter root), not the 21-char raw-OCC form.
  This was wrong in the original code and has been fixed.
- **`get_stock_bars` takes `symbols` (plural) and `days`**, not `symbol`.
- **`get_option_chain` needs real filters to be useful.** An unfiltered call returns an
  arbitrary ~100-contract page with no relation to spot (came back all deep-ITM calls,
  hundreds of dollars from the actual underlying price). Always pass
  `expiration_date_gte`/`_lte` (the locked DTE band) and `strike_price_gte`/`_lte`
  (a window around spot) -- `strategy/chain.py:fetch_and_slice_chain` does this.
- Live end-to-end proof: `fetch_and_slice_chain("SPY")` returns real viable short/long
  candidates with sane deltas (confirmed ~0.20-0.23Δ short, ~0.13-0.15Δ long on a real
  chain pull), and `scripts/run_once.py --symbol SPY` runs the full real pipeline
  (bars → regime → chain → gate) end to end. It correctly stood down on `cheap_iv_rv`
  rather than forcing a trade.
- **Still open**: neither `FEATHERLESS_API_KEY` nor `ANTHROPIC_API_KEY` are set yet, so
  no live proposer call has actually been proven end-to-end. `agents/llm.py` now fails
  over Featherless → Claude live (not just as an offline debug path) once both keys
  exist -- `use_anthropic_fallback` previously did the opposite (blocked Featherless
  instead of enabling a fallback); that's fixed too.

## Prompt memory + news context (added, not in the original plan)

- The proposer's context now also includes `recent_cycles` (a deterministic recap of
  the last 5 cycles for that symbol -- veto reasons, approvals -- read from
  `storage/db.py`, formatted by `agents/prompts.py:format_cycle_recap`) and `headlines`
  (up to 5 recent headlines via `get_news`, formatted by `format_headlines`). Both are
  advisory context only, injected via `agents/cycle.py`'s `recap_fn`/`news_fn` params
  (default: real DB read / real MCP call, both best-effort and never block a cycle on
  failure) -- same DI pattern as `chain_fn`. This is prompt memory, not training; no
  fine-tuning or history store was added.
- **Deliberately not built**: a structured earnings/ex-dividend hard veto. Alpaca's MCP
  only exposes unstructured news text (`get_news`), not a calendar. `event_in_life` on
  `risk/engine.py`'s `ProposalView` exists as a veto slot but nothing sets it yet --
  faking a calendar from headline text would be worse than leaving it unset. If this
  gets built later, ex-dividend/macro-release dates are the right target, not earnings
  (SPY/QQQ/IWM are ETFs, they don't have earnings).
- `get_news`'s live response shape is **unverified** (unlike the option/bars endpoints,
  which were confirmed against real calls) -- `agents/cycle.py`'s `_news()` is
  defensive about the key name (`headline`/`title`/`summary`) for that reason.
