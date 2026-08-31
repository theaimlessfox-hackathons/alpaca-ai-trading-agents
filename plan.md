# Alpaca AI Trading Agents Hackathon — ThetaGate (Grok's book + Claude's wiring + GPT's demo)

## Context

Building a submission for lablab.ai's **Alpaca AI Trading Agents Hackathon** (event window Aug 28–Sep 4, 2026).

### Provisional event constraints

Treat the following as **unverified until `demo-submission/001` reads the live form**. Do not bake them into CLAUDE.md as facts.

- Autonomous agent on Alpaca Trading API plus official MCP and/or CLI (event page emphasizes this).
- Paper trading only.
- Options appear to be required by the Options Alpha Agents track — confirm on the form.
- A dedicated paper account is expected; starting balance and “fresh $100k” copy stay provisional.
- Judging axes and prize split: cited from earlier research, **confirm on the form**.
- **Do not hard-code a clock time.** Use “submit with a multi-hour buffer before the posted deadline.”

**Trading-day math (calendar only):** today is Sunday 30 Aug (market closed). Mon 31 Aug–Fri 4 Sep are US cash sessions. Exact Friday submit cutoff is unknown until 001 closes.

## How this plan came together

Three independently-drafted plans exist in `plans/` in the actual repo: this one (originally a 3-agent Bull/Bear/Risk-Manager debate over directional spreads), `GPT.md` ("Alpaca Sentinel" — human-approval-gated portfolio risk agent), and `Grok.md` ("ThetaGate" — regime-gated premium-selling desk). After comparing all three, the final direction is a deliberate hybrid, not any one plan verbatim:

- **Strategy — from Grok**: defined-risk credit spreads on liquid ETFs, not directional single-stock bets.
- **Agent architecture — simplified from Claude's original 3-way debate**: one proposer + one short critic pass, not a 3-model debate on a fixed timer. Two independent plans (GPT, Grok) converged on fewer agents than the original design; the debate format is cut down accordingly.
- **Execution/safety infrastructure — from Claude's original plan, unchanged**: MCP stdio wrapper, Day-1 schema introspection, the LLM never gets the order-placement tool, deterministic risk engine, kill switch, `alpaca-py` fallback.
- **Ops — from Grok**: two paper accounts, CLI + MCP both in the path, Featherless as the core proposer model (not just a stretch add-on), social calendar, safer submission timing.
- **Demo — from GPT**: a tight reject → critic → fill narrative, plus a seeded replay fallback.

**Explicitly dropped**: GPT's Next.js/FastAPI stack (Streamlit is the right call solo), GPT's options-exclusion mistake (options are mandatory — not following GPT's strategy at all), single-stock directional "lottery ticket" plays, a 3-model debate on a 20-minute timer, a human-click-required approval gate blocking the autonomous loop (a visible manual kill-switch/override button stays in the dashboard, but nothing blocks on a click), and the original 15:00 UTC deadline figure (superseded by 20:00 UTC above).

## What we're building

**ThetaGate**: an autonomous options-selling desk that sells defined-risk credit spreads on SPY/QQQ/IWM when implied vol is rich, stands down (or hedges) when the regime is cheap-vol or breakout, gated by a deterministic Python risk engine, executed through Alpaca's official MCP server (with the Alpaca CLI wired in as a secondary interface), surfaced through a Streamlit dashboard plus an MCP-chat operator interface for the demo.

## Correct project location

The actual hackathon repo is **`/home/first-hassan/win10/Desktop/Projects/Alpacca`** (not the empty `/mnt/c/Users/sai95/Desktop/Projects/Alpacca` this session started in) — a real git repo (`origin` → `github.com:theaimlessfox-hackathons/alpaca-ai-trading-agents.git`, branch `main`) already containing `plans/GPT.md`, `plans/Grok.md`, and `README.md`. All implementation work goes there.

## First implementation step: write CLAUDE.md

Before other Day-1 work, create `CLAUDE.md` at the repo root capturing this plan's durable context (hackathon constraints/deadline, project structure, the non-negotiable safety invariant, risk parameters, locked strategy spec, day-by-day schedule with today's position) so every future Claude Code session in this repo has it automatically loaded. Update it as the build progresses (e.g. once the real `place_option_order` schema is introspected) so it stays the single source of truth.

## Verified facts / unknowns to check Day 1

- **alpaca-mcp-server**: stdio transport by default (or `--transport streamable-http`); env vars `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER_TRADE=true`. Tool inventory includes account/portfolio reads, positions, options data (`get_option_chain`, `get_option_snapshot` w/ Greeks+IV, `get_option_bars`, quotes/trades), a unified `place_option_order` tool for single- and multi-leg orders, order management, stock data, news, watchlists, market-clock tools.
  - **Unverified**: `place_option_order`'s exact JSON schema isn't documented in prose — introspect via `list_tools()` before writing order-construction code.
- **Alpaca options levels**: Level 3 is required for multi-leg spreads. Grok's research claims paper accounts already ship at Level 3 by default — plausible, but confirm on both accounts Day 1 rather than assume.
- **Featherless integration is a new, unverified dependency**: confirm its API surface (base URL, auth, whether it exposes an OpenAI-compatible chat/completions endpoint, whether it supports function-calling or JSON mode) as part of Day-1 setup, same priority as the MCP schema check.
- **Structured-output reliability risk**: the original design leaned on Claude's native structured outputs for the trade-decision contract. Featherless-hosted open-weight models are meaningfully less reliable at strict JSON schema adherence. Since this is now the model on the safety-critical decision path, `agents/schemas.py` must validate the proposer's output against the pydantic `TradeDecision` model with **a parse-and-retry loop** (re-prompt with the validation error on failure, cap at ~2–3 retries, hard-fail closed — no trade — if it still won't parse) rather than assuming clean JSON comes back. Keep Claude Sonnet 5 available as a dev-time fallback model for debugging this path, even though it isn't the demoed model.

## Locked strategy spec (do not change mid-week)

- **Universe**: SPY / QQQ / IWM only. No single-stock directional plays.
- **Structures**: put/call credit spreads only. Iron condors are out of scope this week.
- **DTE**: 7–21.
- **Delta targets**: short leg ~0.20–0.30, long leg ~0.10–0.15.
- **Regime gate**: trade only when the **IV/RV ratio** is rich — ATM implied vol divided by 20-day annualized realized vol from daily bars. Do **not** call this IV rank (that needs a stored IV history we will not build). Stand down when IV/RV is cheap or a simple ATR/range breakout flag is on. Deterministic Python (`strategy/regime.py`), not an LLM call.
- **Exits** (autonomous, not just “no new orders”): take profit at 40–60% of credit captured; stop at a defined loss multiple of credit; flatten on halt or regime reversal; cancel entry orders still unfilled after a timeout. Expiry sweep (≤2 DTE) is backup only — it will probably not fire this week.
- **P&L target framing**: small positive or flat with bounded drawdown and a full audit trail — not a swing for a big number. This is the safer bet given only ~4–5 live trading days.

## Architecture: LLM proposes, deterministic code gates and executes

```
Alpaca market data (bars, option chain, Greeks, news)      ← MCP + CLI
        │
        ▼
 Regime / feature layer            ← deterministic Python (strategy/regime.py)
 (ATM IV / 20d RV, liquidity, DTE)
        │
        ▼
 Proposer agent                    ← Featherless LLM
 "propose a credit spread: strikes, size, thesis" — structured TradeProposal, parse+retry validated
        │
        ▼
 Critic pass                       ← WAVE 2, after first complete sandbox trade
 one short LLM call, advisory only; not on the Sunday critical path
        │
        ▼
 Risk engine                       ← NO LLM, pure functions, re-validates everything independently
        │
        ▼
 Executor                          ← MCP place_option_order (primary) / alpaca-py fallback
        │
        ▼
 Streamlit dashboard + MCP-chat operator surface + Alpaca CLI (cron-style ops)
```

**The non-negotiable safety invariant**: `place_option_order` is never given to any LLM call — not the proposer, not the critic. Both only ever produce text/structured output. `execution/executor.py` is the only code path that calls it, and only after `risk/engine.py` independently re-validates every limit against the proposal — it does not trust that the LLM respected the limits it was told. LLM judgment is advisory; code is authoritative over anything that moves money.

Fallback if the introspected `place_option_order` schema proves broken under time pressure: `execution/alpaca_py_fallback.py` submits the multi-leg order directly via `alpaca-py`'s `TradingClient.submit_order()` with `OrderClass.MLEG` + `OptionLegRequest` legs.

## Project structure

```
Alpacca/
  .env.example / .env (gitignored)   # ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_PAPER_TRADE=true, FEATHERLESS_API_KEY, ANTHROPIC_API_KEY
  requirements.txt                    # mcp, alpaca-py, streamlit, pydantic, pydantic-settings, apscheduler, python-dotenv, pandas, requests/openai-client for Featherless, anthropic (dev fallback)
  config/
    settings.py          # pydantic-settings: risk limits, delta/DTE targets, model name, cadence
  mcp_integration/
    server_manager.py     # spawns/supervises the alpaca-mcp-server subprocess; auto-restart on crash/hang
    client.py             # async wrapper: connect(), call_tool(name, args), list_tools() for schema introspection
  cli_integration/
    ops.py                 # thin wrapper invoking the official `alpaca` CLI for cron-style account/positions/order ops — satisfies "MCP or CLI, use both" and demoable as a stack-usage point
  tools/
    schema_introspect.py  # ONE-OFF Day-1 script dumping real schemas for place_option_order, get_option_chain, etc.
    research_tools.py     # tool defs wrapping read-only MCP calls (chain/Greeks, bars, news, clock)
    account_tools.py      # tool defs wrapping account/position/portfolio-history reads
  agents/
    prompts.py            # system prompts: proposer, critic
    schemas.py             # pydantic models: TradeProposal, CriticNote — parse+retry validation lives here
    proposer.py            # run_proposer(candidate, market_context, portfolio_state) -> TradeProposal (Featherless)
    critic.py               # run_critic(TradeProposal) -> CriticNote (one short paragraph, advisory only)
    cycle.py                 # orchestrates one cycle: candidate -> proposer -> critic -> risk engine -> decision + transcript
  strategy/
    regime.py                # deterministic IV-rank / RV-vs-IV / breakout-regime gate — decides whether to even ask the proposer
    signals.py                # SPY/QQQ/IWM candidate loop only
    structures.py              # TradeProposal -> exact place_option_order payload (single place this logic lives)
  risk/
    engine.py                  # RiskEngine.validate(proposal, portfolio_state, daily_pnl) -> Approve | Veto(reason)
    kill_switch.py              # daily-loss monitor, control-flag read/write, expiry-sweep logic
  execution/
    executor.py                 # deterministic: approved TradeProposal -> payload -> mcp place_option_order -> log
    alpaca_py_fallback.py         # Plan B: direct alpaca-py multi-leg submission
  scheduler/
    loop.py                       # market-hours-aware cycle cadence, kill-switch checks, snapshot writer, expiry sweep
    market_hours.py                # is_market_open()/next_open/close via get_clock, ET timezone handling
  storage/
    db.py                          # SQLite: cycles, decisions, orders, equity_history, positions_snapshot
    logger.py                       # structured logging (console + JSONL) — demo evidence trail
  dashboard/
    app.py                          # Streamlit entrypoint
    components.py                    # chart/table render helpers
  scripts/
    setup_check.py                   # Day-1 sanity: env vars, MCP connect, CLI connect, Featherless smoke call, get_account_info, get_clock, options level
    run_once.py                       # manually trigger one cycle end-to-end for a given ticker
    replay_demo.py                     # GPT-style seeded replay: given a saved market snapshot, re-run proposer->critic->risk engine for demo/recording use if live data misbehaves
  tests/
    test_risk_engine.py               # highest-ROI tests given time budget — pure logic, no network calls
    test_regime.py
    test_structures.py
  logs/                                # gitignored
  docs/
    WRITEUP.md
    ARCHITECTURE.md
```

## Agent cycle (simplified from a 3-way debate)

- **Proposer** (`agents/proposer.py`, Featherless): sees the candidate ticker, current regime/IV-rank read from `strategy/regime.py`, recent bars/news, and the option chain near the target deltas. Outputs a `TradeProposal`: structure type, expiration, legs (strikes/deltas), limit price, size, thesis, confidence. This is the model targeting the Featherless partner prize.
- **Critic** (`agents/critic.py`, one short Featherless call): given the `TradeProposal`, produces a single-paragraph rebuttal/"what would change my mind" note — advisory only, feeds the demo narrative ("Challenge this trade") and the dashboard transcript. Not a second full agent with its own tool access.
- **Risk engine** (`risk/engine.py`, no LLM): the actual gate. Independently recomputes every limit — position count, per-trade max loss, daily loss budget, delta/DTE band, IV sanity, liquidity sanity — against the `TradeProposal`, regardless of what the proposer claimed. Approve or Veto(reason).
- Every cycle, whether traded or not, is logged in full (`storage/db.py` + `storage/logger.py`) — this is what feeds both the dashboard's transcript viewer and the social posts about rejected trades.

## Risk / kill-switch parameters (starting values, tune Day 2)

- Universe: SPY/QQQ/IWM only; max 3 open structures total; max 1–2 per underlying.
- Max loss per structure: ≤2% of the $100k competition account NAV.
- Daily loss halt: −3% of start-of-day equity. Total drawdown halt: −8% of starting capital. Either halts new orders for the rest of the day/week respectively.
- DTE band: 7–21 (locked spec). Daily expiry-sweep closes anything inside 2 trading days — no rolling/assignment logic in scope.
- Delta band: short leg 0.20–0.30, long leg 0.10–0.15 — reject proposals outside this band.
- IV sanity check (reject if ATM IV outside a sane band) and bid-ask sanity check (reject if spread too wide relative to mid) — guards against stale/thin data.
- No overlapping shorts on the same underlying; buying-power check before every order; no trade if a same-underlying earnings date falls inside the position's life.
- 60–90 min cooldown per underlying (cost/thrash control).
- Master kill switch: DB/file flag checked by both scheduler and executor before any order; dashboard has a manual STOP toggle — visible, but nothing in the autonomous loop blocks on a human click.

All limits live as constants in `config/settings.py`; enforcement is pure functions in `risk/engine.py` and `strategy/regime.py`, unit-tested with no network calls (`tests/test_risk_engine.py`, `tests/test_regime.py`) — this is the code that most needs to be correct.

## Two-account pattern

1. **Sandbox account** — created today, used for all testing/breaking-things (schema introspection, first order placements, debugging fills). Never counted.
2. **Competition account** — a second, brand-new $100k paper account created specifically for judging, untouched until the loop is proven on the sandbox. Its ID gets disclosed in the submission; its portfolio history is the P&L evidence. Switch the live scheduler to this account's keys before Monday's open.

## Scheduler (`scheduler/loop.py`) and CLI/MCP-chat operator surface

- Checks `get_clock`; sleeps when market closed.
- During market hours: runs one cycle per candidate (SPY, QQQ, IWM) on a cadence (~20–30 min is fine — the single-proposer design is cheap/fast, cadence isn't the bottleneck).
- Separate tighter loop (~5 min): reconcile open orders with Alpaca, apply exit policy, flatten if a halt fires, snapshot equity/positions.
- End-of-day: summary log. Expiry sweep is backup only.
- MCP: start a local stdio server and keep a basic connection. Auto-restart supervisor is **wave 2** (after `list_tools` works).
- **CLI**: one demonstrated read (`account` or `positions`) via official `alpaca` CLI. No second executor.
- **Alpaca MCP chat (demo only)**: official server answers account, positions, orders, and market data. It **cannot** explain ThetaGate trades, toggle our kill switch, or show our risk budget. Do not claim those. Halt is the Streamlit STOP / `logs/KILL` flag. Last-trade explanation is the dashboard transcript.

## Dashboard (`dashboard/app.py`, Streamlit)

Header (live equity, daily P&L, open positions, kill-switch/halt status) → equity curve → open positions table → trade history table → **proposal/verdict transcript** (TradeProposal, RiskEngine verdict + reason, rejected proposals first-class) → activity feed → manual STOP. “Run cycle now” is **wave 2**. Critic pane is wave 2. Data source: SQLite via `storage/db.py`.

## Social-media content calendar (targets the $1,000 social-engagement prize track)

**Not on the code critical path.** Five posts (X + LinkedIn) if time exists after a sandbox fill. Tag lablab + Alpaca. Show vetoes, not a rocket P&L screenshot:
1. **Today (Sun)**: architecture post — proposer/critic/risk-engine concept.
2. **Mon**: first live decision transcript, specifically including a **rejected** proposal.
3. **Tue/Wed**: a setback and the fix (bad fill, kill-switch trigger, bug).
4. **Thu**: a short demo clip of the dashboard/transcript viewer.
5. **Fri**: results + repo link.

## Submission checklist

- Public GitHub repo. Hosted/live demo (Streamlit Cloud/Railway are reasonable).
- One-page write-up covering AI logic, risk gates, and Alpaca infra usage (MCP + CLI + API).
- Slides deck.
- Demo video: prepare **MP4 ≤5 min** (generic lablab). Confirm widget on the logged-in form.
- Competition paper account ID on the submission (event page).
- Submit with a buffer before **4 Sep 20:00 UTC** (event schedule: 9:00 PM Bangladesh Standard Time). Wizard clock still unopened.

## Demo script (GPT's ~90-second core, inside the ≤5 min video)

1. One-line hook: sells defined-risk premium when IV/RV is rich, stands down otherwise, Python vetoes the model.
2. Live desk: proposal → risk engine reject (show a real veto) → a different proposal → fill → monitor/reconcile.
3. Show Alpaca MCP chat for **account/positions only**, plus one official CLI read. Halt and “why this trade” live on the Streamlit desk, not in Alpaca MCP.
4. Show the same order/position in Alpaca's own paper account UI (cross-verification).
5. Equity curve, max loss, why the gates exist.
6. Stack recap (Trading API + MCP + CLI + Featherless) and what's next.

Keep a **seeded replay script** (`scripts/replay_demo.py`) ready as a fallback: given a saved market snapshot, re-run proposer → critic → risk engine deterministically, in case live market data misbehaves during recording.

## Day-by-day schedule (provisional deadline — confirm in demo-submission/001)

Credible solo load is **65–80 hours** including integration, live watch, and submission. Sunday is **not** “build the whole desk.”

- **Sun (P0)**: Verify lablab form fields. Create sandbox + competition paper accounts; confirm options level. Scaffold + settings. MCP `get_account_info` + schema dump. Regime as IV/RV + risk tests. `TradeProposal` parse+retry. Executor **dry-run**. One CLI read. No critic, no dashboard polish, no social required.
- **Mon**: `run_once` sandbox cycle (veto or small spread). Order lifecycle: reconcile, cancel unfilled, flatten on halt. **Do not** switch to the competition account until sandbox cycle + account-guard invariants pass.
- **Tue**: Competition activation (explicit flag + expected account ID + paper-only). Scheduler on judged account. Desk shell + transcript of reject/fill. Replay fixture.
- **Wed**: Exit-policy tuning, fill quality, WRITEUP draft. Critic LLM only if the book is already live.
- **Thu**: Freeze. Video. Slides. Hosted URL.
- **Fri**: Submit with a buffer. No rewrites.

### Cut from the critical path

Iron condors · custom CLI beyond one read · critic LLM · MCP auto-restart supervisor · “run cycle now” queue · social posts as blockers · a custom ThetaGate MCP server.

## Key risks to watch

1. `place_option_order` schema is undocumented in prose — resolve via `list_tools()` Day 1; keep the `alpaca-py` fallback ready.
2. Featherless API surface and structured-output reliability are unverified — smoke-test Day 1, build the parse+retry validation loop before relying on it for live trades.
3. Paper account options level may default below Level 3 — verify explicitly on both accounts rather than assume, even though Grok's research suggests it's fine.
4. Greeks/IV fidelity on paper trading is unconfirmed — validate real values Day 1.
5. Only ~4–5 tradable days in the window — a working live loop by Monday close is critical for P&L evidence.
6. Multi-hour unattended MCP subprocess runs risk crashes/hangs — ship a **basic start/stop lifecycle first**; auto-restart supervisor is **wave 2**.
7. Multi-leg order fill behavior in paper trading may differ from single-leg — test small Monday, log mid vs. fill.
8. lablab.ai's exact submission form fields (video format, one-pager, slides) are unconfirmed — check Day 1–2, not on deadline day.
9. Short-premium strategies carry real (simulated) tail risk if the regime gate misfires — the −3%/−8% halts and delta/DTE bands are the main defense; don't loosen them under pressure to chase P&L.

## Critical files (build/get-right order)

1. `mcp_integration/client.py` — the MCP stdio wrapper everything else depends on.
2. `tools/schema_introspect.py` — resolves the undocumented `place_option_order` schema before any order code is written.
3. `agents/schemas.py` — the parse+retry validation contract that makes a Featherless-hosted proposer safe to sit upstream of a risk gate.
4. `risk/engine.py` + `strategy/regime.py` — the deterministic, LLM-independent gates; correctness here matters most.
5. `scheduler/loop.py` — the unattended market-hours loop that determines how many live trading days generate P&L evidence.

## Verification

- `scripts/setup_check.py`: confirms env vars, MCP server connects, CLI connects, Featherless smoke call succeeds, `get_account_info`/`get_clock`/options-level all return sane values on both accounts.
- `scripts/run_once.py`: manually trigger one full cycle for a single ticker end-to-end and inspect the transcript + (if triggered) the resulting order, cross-checked against Alpaca's own paper trading dashboard.
- `tests/test_risk_engine.py` / `test_regime.py` / `test_structures.py`: run via `pytest`, no network required.
- Live verification: once the scheduler is running (Monday+), watch the Streamlit dashboard update in real time during market hours, and independently confirm placed orders/positions match Alpaca's own paper account UI.
- Before submitting: run `setup_check.py` against a fresh clone/checkout to confirm the whole thing is reproducible from the repo alone.
