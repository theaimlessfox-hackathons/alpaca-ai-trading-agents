# Alpaca AI Trading Agents Hackathon — Bull/Bear/Risk-Manager Options Agent

## Context

Building a submission for lablab.ai's **Alpaca AI Trading Agents Hackathon** (Aug 28–Sep 4, 2026, deadline Sep 4 15:00 UTC — ~6 days remaining from today, Aug 29). Requirements confirmed via research:

- Autonomous AI trading agent using Alpaca's Trading API + Alpaca's official MCP Server (`alpacahq/alpaca-mcp-server`).
- Must run in Alpaca's paper trading environment (real market data, simulated funds).
- **Must incorporate options trading** (hard requirement).
- Submission needs a **new, dedicated Alpaca paper account** created specifically for this hackathon.
- Judged on **P&L** and **creativity/engagement**. $6,000 prize pool ($2500/$1500/$1000 + 2 social-engagement awards). Solo build.

The working directory is empty — this is a from-scratch build. Confirmed design direction: **Python**, a **Bull / Bear / Risk-Manager multi-agent debate** system (Claude Sonnet 5 via Anthropic API), trading **defined-risk directional options spreads** (debit/credit verticals), with a deterministic, non-LLM execution/risk layer and a Streamlit dashboard for the demo.

**Trading-day math for this window**: Aug 30 is Sunday (market closed). Aug 31–Sep 3 are full trading days. Sep 4 is a partial session before the 15:00 UTC deadline (~1.5h after 9:30 AM ET open). Getting the live loop running by end of Day 3 (Aug 31) is the single highest-priority milestone — every extra day it runs live is more P&L evidence.

## First implementation step: write CLAUDE.md

Before any other Day 1 work, create `CLAUDE.md` at the repo root capturing this plan's durable context so every future Claude Code session in this repo (not just this one) has it automatically loaded — hackathon constraints and deadline, the project structure below, the non-negotiable safety invariant (no LLM call is ever given the `place_option_order` tool; only `execution/executor.py` calls it, gated by `risk/engine.py`), the risk/kill-switch parameters, and the day-by-day schedule with today's position in it. Keep it updated as the build progresses (e.g., once the real `place_option_order` schema is introspected, record it there) so it stays the single source of truth instead of this plan file.

## Verified facts driving the design

- **alpaca-mcp-server** (confirmed live from GitHub): stdio transport by default (or `--transport streamable-http`); env vars `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER_TRADE=true`. Full tool inventory includes account/portfolio reads, positions, options data (`get_option_chain`, `get_option_snapshot` w/ Greeks+IV, `get_option_bars`, quotes/trades), a single unified `place_option_order` tool for both single-leg and multi-leg orders, generic order management, stock data, news, watchlists, and market-clock tools.
  - **Unverified/must-check Day 1**: the exact JSON schema of `place_option_order` isn't documented in prose — must introspect via the MCP client's `list_tools()` before writing order-construction code.
- **Alpaca options levels**: Level 3 is required for multi-leg spreads. Paper-account default level is *not* documented — must explicitly verify/enable via `get_account_config`/`update_account_config` or the dashboard, don't assume it's on.
- **Claude Sonnet 5**: use `output_config: {effort: ...}` (medium for Bull/Bear, high for Risk Manager), **structured outputs** (`output_config.format` / `client.messages.parse()`) for the Risk Manager's `TradeDecision`, and **prompt caching** (`cache_control: ephemeral`) on the static system prompts/tool defs since they repeat every debate cycle for days. Intro pricing ($2/$10 per MTok) runs through 2026-08-31 — not a design driver, just a minor cost note.

## Architecture decision: don't let the LLM execute trades directly

Run `alpaca-mcp-server` as a **local stdio subprocess**, talked to by your own orchestrator via the `mcp` Python client library — not via Claude's native remote MCP connector (which executes tool calls server-side on Anthropic's infra, removing your ability to gate order placement) and not primarily via the Claude Agent SDK (built for coding-agent workflows, not verified safe for this money-moving gating use case).

Wrap each needed MCP tool as a plain Python function exposed to Claude as an ordinary tool. **`place_option_order` is never given to any LLM call, including the Risk Manager.** The Risk Manager only emits a structured `TradeDecision` JSON. A separate deterministic module (`execution/executor.py`) is the only code path that calls `place_option_order`, and only after `risk/engine.py` independently re-validates every limit (it does not trust that the LLM respected the limits it was told). This is the core safety property: LLM judgment is advisory, code is authoritative over anything that moves money.

Fallback if the introspected `place_option_order` schema proves broken under time pressure: `execution/alpaca_py_fallback.py` submits the multi-leg order directly via `alpaca-py`'s `TradingClient.submit_order()` with `OrderClass.MLEG` + `OptionLegRequest` legs — keep as backup only, since routing through the official MCP server is the compliance requirement.

## Project structure

```
Alpacca/
  .env.example / .env (gitignored)   # ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER_TRADE=true, ANTHROPIC_API_KEY
  requirements.txt                    # anthropic, mcp, alpaca-py, streamlit, pydantic, pydantic-settings, apscheduler, python-dotenv, pandas
  config/
    settings.py          # pydantic-settings: risk limits, model name, cadence, watchlist path
    watchlist.py          # curated liquid, optionable large-caps/ETFs (SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMZN, META...)
  mcp_integration/
    server_manager.py     # spawns/supervises the alpaca-mcp-server subprocess; auto-restart on crash/hang
    client.py             # async wrapper: connect(), call_tool(name, args), list_tools() for schema introspection
  tools/
    schema_introspect.py  # ONE-OFF Day-1 script dumping real schemas for place_option_order, get_option_chain, etc.
    research_tools.py     # Claude-facing tool defs wrapping read-only MCP calls (stock/news/options data)
    account_tools.py      # Claude-facing tool defs wrapping account/position/portfolio-history reads (Risk Manager only)
  agents/
    prompts.py            # system prompts: bull, bear, risk_manager
    schemas.py             # pydantic models: BullCase, BearCase, TradeDecision (drives output_config.format)
    bull.py                # run_bull(ticker, market_context) -> BullCase
    bear.py                # run_bear(ticker, market_context, bull_case) -> BearCase (sees Bull's output — real rebuttal)
    risk_manager.py         # run_risk_manager(ticker, bull_case, bear_case, portfolio_state, risk_budget_text) -> TradeDecision
    debate.py                # orchestrates one cycle: candidate -> bull -> bear -> risk_manager -> TradeDecision + transcript
  strategy/
    signals.py               # candidate sourcing: watchlist + get_market_movers/get_most_active_stocks
    iv.py                     # realized-vol-vs-IV proxy from get_stock_bars + get_option_snapshot; logs IV history
    structures.py              # TradeDecision -> exact place_option_order payload (single place this logic lives)
  risk/
    engine.py                  # RiskEngine.validate(decision, portfolio_state, daily_pnl) -> Approve | Veto(reason)
    kill_switch.py              # daily-loss monitor, control-flag read/write, expiry-sweep logic
  execution/
    executor.py                 # deterministic: approved TradeDecision -> payload -> mcp place_option_order -> log
    alpaca_py_fallback.py         # Plan B: direct alpaca-py multi-leg submission
  scheduler/
    loop.py                       # market-hours-aware debate cadence, kill-switch checks, snapshot writer, expiry sweep
    market_hours.py                # is_market_open()/next_open/close via get_clock, ET timezone handling
  storage/
    db.py                          # SQLite: debates, decisions, orders, equity_history, positions_snapshot
    logger.py                       # structured logging (console + JSONL) of every agent turn/decision — demo evidence
  dashboard/
    app.py                          # Streamlit entrypoint
    components.py                    # chart/table render helpers
  scripts/
    setup_check.py                   # Day-1 sanity: env vars, MCP connect, get_account_info, get_clock, options level
    run_once.py                       # manually trigger one debate cycle end-to-end for a given ticker
  tests/
    test_risk_engine.py               # highest-ROI tests given time budget — pure logic, no API calls
    test_structures.py
  logs/                                # gitignored
  docs/
    WRITEUP.md
    ARCHITECTURE.md
```

## Debate loop

- **Bull agent** (`agents/bull.py`): tools = `get_stock_snapshot`, `get_stock_bars`, `get_news`, `get_option_chain`/`get_option_snapshot`, `get_clock`. Builds the strongest evidence-grounded bullish case, cites tool-sourced facts, proposes a directional structure hint + timeframe, must acknowledge one real risk. Output: `BullCase{thesis, evidence[], suggested_structure, target_move_pct, timeframe_days, confidence}`.
- **Bear agent** (`agents/bear.py`): same tools **plus the full BullCase as input** — must explicitly rebut it. Output: `BearCase{counter_thesis, key_risks[], rebuttal_to_bull[], confidence, recommended_action}`.
- **Risk Manager** (`agents/risk_manager.py`): sees ticker, BullCase, BearCase, and a portfolio-state + numeric risk-budget summary computed by `risk/engine.py` (not by LLM judgment). Tools = read-only account/portfolio + option chain/snapshot (never `place_option_order`). Output via strict `output_config.format`: `TradeDecision{action, ticker, structure_type, expiration_date, legs[], limit_price, quantity, est_max_loss, est_max_gain, rationale, confidence}`.

## Risk / kill-switch parameters (starting values, tune Day 2)

- Max 5 concurrent open positions; max 1–2 structures per underlying.
- Max loss per trade: 1–2% of NAV.
- Daily loss cap / kill switch: 3% of start-of-day equity — halts new orders for the rest of the day on breach.
- Expiry buffer: only trade 14–60 DTE; daily expiry-sweep closes anything within 2 trading days (no rolling/assignment logic — out of scope for 6 days).
- IV sanity check (reject if ATM IV outside ~5%–250%) and bid-ask sanity check (reject if spread > ~15–20% of mid) to guard against stale/thin data.
- 60–90 min cooldown per ticker (cost/thrash control).
- Master kill switch: DB/file flag checked by both scheduler and executor before any order; dashboard has a manual STOP toggle.

All limits live as constants in `config/settings.py`; enforcement is pure functions in `risk/engine.py`, unit-tested with no network calls (`tests/test_risk_engine.py`) — this is the code that most needs to be correct.

## Scheduler (`scheduler/loop.py`)

- Checks `get_clock`; sleeps when market closed.
- During market hours: cycles through ~3–5 candidates every 20–30 min, one debate per candidate (sequential, easier to log).
- Separate tighter loop (~5 min): kill-switch/daily-loss check + equity/positions snapshot, decoupled from debate cadence.
- End-of-day job: expiry sweep + summary log entry.
- Subprocess supervisor around the MCP connection with auto-reconnect — this runs unattended for multi-hour stretches across 4+ trading days.

## Dashboard (`dashboard/app.py`, Streamlit)

Header (live equity, daily P&L, open positions, kill-switch status) → equity curve → open positions table → trade history table → **debate transcript viewer** (Bull case, Bear rebuttal, Risk Manager decision + rationale, RiskEngine verdict — including passed-on trades, this is the key artifact for the creativity/engagement score) → activity feed → manual kill-switch toggle / "run cycle now" button. Follow the `dataviz` skill's palette/layout guidance when building charts and stat tiles. Data source: SQLite via `storage/db.py`.

## Day-by-day schedule

- **Day 1 (Sat Aug 29, today)**: Create the new dedicated Alpaca paper account; explicitly verify/enable options Level 3; confirm Anthropic API key; install `alpaca-mcp-server`, run `tools/schema_introspect.py` to dump the real `place_option_order`/`get_option_chain`/`get_option_snapshot` schemas; verify Greeks/IV populate sanely in paper trading; scaffold repo structure; get one end-to-end round trip (`mcp_integration/client.py` → `get_account_info`) working; check the actual lablab.ai submission form fields now, not later.
- **Day 2 (Sun Aug 30, market closed)**: Build `prompts.py`, `bull.py`, `bear.py`, `risk_manager.py` with structured output; verify `TradeDecision` parses reliably across repeated runs. Build `strategy/structures.py` against the real Day-1 schema. Build `risk/engine.py` + unit tests before touching live orders.
- **Day 3 (Mon Aug 31, first live trading day)**: Wire `executor.py` (+ fallback), `storage/`, `scheduler/loop.py`/`market_hours.py`. Run the full loop live, watch closely, fix bugs live. Goal: unattended loop running by end of day.
- **Day 4 (Tue Sep 1)**: Build the full dashboard. Keep the loop running; fix overnight issues; start `ARCHITECTURE.md`.
- **Day 5 (Wed Sep 2)**: Bug-fix backlog, prompt tuning from observed agent behavior, retry/backoff on MCP + Anthropic calls, prompt-caching pass. Start `WRITEUP.md`, capture dashboard screenshots.
- **Day 6 (Thu Sep 3)**: Final full live session in the morning. Afternoon: freeze code, run `setup_check.py` against a clean checkout, record the ~3–5 min demo video (dashboard, one full debate transcript walkthrough, an order cross-verified in Alpaca's own paper UI, equity curve, risk-engine/kill-switch explanation). Finalize write-up, confirm `.env` gitignored and no leaked keys.
- **Day 7 (Fri Sep 4, deadline 15:00 UTC / 11:00 AM ET)**: Optional final ~1–1.5h live session for one more data point. Final review of write-up/video/repo. **Submit with a 2–3 hour buffer** — don't cut it close. Include a portfolio-history screenshot/export from the dedicated paper account as P&L evidence.

## Key risks to watch

1. `place_option_order` schema is undocumented in prose — resolve via `list_tools()` Day 1; keep the `alpaca-py` fallback ready.
2. Paper account options level may default below Level 3 — verify/enable explicitly before assuming spreads will work.
3. Greeks/IV fidelity on paper trading is unconfirmed — validate real values Day 1.
4. Only ~4.15 tradable days in the window — a working live loop by Day 3 is critical for P&L evidence.
5. Multi-hour unattended MCP subprocess runs risk crashes/hangs — build the supervisor up front, don't discover this during the live demo.
6. Multi-leg order fill behavior in paper trading may differ from single-leg — test small on the first live day.
7. lablab.ai's exact submission form fields are unconfirmed — check Day 1–2, not on deadline day.
8. Anthropic API cost/rate limits across a multi-day scheduled loop — mitigate with prompt caching, moderate effort levels, 20–30 min cadence.

## Critical files (build/get-right order)

1. `mcp_integration/client.py` — the MCP stdio wrapper everything else depends on.
2. `tools/schema_introspect.py` — resolves the undocumented `place_option_order` schema before any order code is written.
3. `risk/engine.py` — the deterministic, LLM-independent risk gate; correctness here matters most.
4. `agents/schemas.py` + `agents/risk_manager.py` — the structured-output contract bridging LLM judgment to code-enforced execution.
5. `scheduler/loop.py` — the unattended market-hours loop that determines how many live trading days generate P&L evidence.

## Verification

- `scripts/setup_check.py`: confirms env vars, MCP server connects, `get_account_info`/`get_clock`/options-level all return sane values.
- `scripts/run_once.py`: manually trigger one full debate cycle for a single ticker end-to-end and inspect the transcript + (if triggered) the resulting order, cross-checked against Alpaca's own paper trading dashboard.
- `tests/test_risk_engine.py` / `test_structures.py`: run via `pytest`, no network required — validates limit enforcement and order-payload construction logic in isolation.
- Live verification: once the scheduler is running (Day 3+), watch the Streamlit dashboard update in real time during market hours, and independently confirm placed orders/positions match what Alpaca's own paper account UI shows.
- Before submitting: run `setup_check.py` against a fresh clone/checkout to confirm the whole thing is reproducible from the repo alone.
