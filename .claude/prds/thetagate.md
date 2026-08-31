---
name: thetagate
description: Autonomous defined-risk options premium desk for the Alpaca AI Trading Agents Hackathon
status: active
created: 2026-08-30T19:10:48Z
---

# PRD: thetagate

## Executive Summary

ThetaGate is an autonomous paper-trading desk that sells defined-risk credit spreads on SPY, QQQ, and IWM when implied vol is rich, and stands down when vol is cheap or the market is breaking out. A Featherless model proposes the structure. A one-paragraph critic challenges it for the demo. A deterministic Python risk engine is the only thing that can approve spending. Orders go out through Alpaca MCP (`place_option_order`), with an `alpaca-py` fallback and the official Alpaca CLI in the ops path.

This is the lablab.ai × Alpaca hackathon submission. Treat “Fri 4 Sep 2026, 21:00 BST / 20:00 UTC” and MP4-upload as **provisional until `demo-submission/001` reads the live form**. Judges (per event copy) score P&L, Alpaca stack usage, originality, and presentation; confirm on the form.

## Problem Statement

Most hackathon options bots pick a direction and blow up, or they are chat UIs that never place a multi-leg order. The brief requires all three of: an autonomous agent, Alpaca MCP **or** CLI, and options in every strategy. A 5-session paper window rewards bounded premium selling with an audit trail more than a directional lottery.

Operators (the builder during the week, judges on the video) need to see: why a trade was proposed, why it was vetoed or filled, current risk, and a kill switch that works without asking the model.

## User Stories

### US-1 — Autonomous premium cycle
As the competition account, I want the desk to scan SPY/QQQ/IWM on a market-hours cadence and sell a put or call credit spread when the regime gate says vol is rich, so the week can produce judged P&L without a human click.

**Acceptance:**
- Given market open, kill switch off, and a rich-vol regime on SPY, when a cycle runs, the system either places a 7–21 DTE credit spread inside the delta band or records a veto with a reason.
- Given a cheap-vol or breakout regime, the proposer is not asked and no order is sent.
- The LLM never receives `place_option_order` or any other order-placement tool.

### US-2 — Deterministic veto
As the risk engine, I want to recompute every limit myself, so a bad JSON proposal cannot spend money.

**Acceptance:**
- Reject if universe ≠ {SPY, QQQ, IWM}, DTE outside 7–21, short delta outside 0.20–0.30, long delta outside 0.10–0.15, max loss > 2% NAV, >3 open structures, overlapping shorts, wide bid-ask, insane IV, earnings inside the life of the trade, daily −3% halt, or total −8% halt.
- Unit tests cover each rule with no network.

### US-3 — Operator desk
As a judge watching the demo, I want a Streamlit timeline of event → evidence → proposal → critic → risk verdict → fill/reject, so I can understand the agent in 90 seconds.

**Acceptance:**
- Dashboard shows live equity, daily P&L, positions, kill-switch state, equity curve, trade history, and full transcripts including rejected proposals.
- Manual STOP toggle exists and flattens plus blocks new orders. “Run cycle now” is wave 2.
- Seeded replay reproduces a saved snapshot if live data dies during recording.

### US-4 — Alpaca stack visibility
As a judge scoring technology implementation, I want MCP, CLI, and the Trading API all in the path.

**Acceptance:**
- Live loop places multi-leg orders via official MCP (or logged fallback).
- One official `alpaca` CLI read (account or positions) is demoed.
- Demo MCP chat is limited to Alpaca account/positions/orders/market. Halt and last-trade explanation are on the Streamlit desk.

### US-5 — Two-account ops
As the submitter, I want a sandbox account for breakage and a fresh $100k competition account for judging.

**Acceptance:**
- Sandbox is used for schema dumps and first fills.
- Competition account is brand new, $100k, unused until the loop is proven.
- Only the competition account ID is disclosed. Scheduler points at it before Monday 9:30 ET.

### US-6 — Submission pack
As the submitter, I want the required lablab artifacts ready Thursday night.

**Acceptance:**
- Public GitHub, hosted Streamlit demo, one-pager (AI logic, risk gates, Alpaca infra), slides, ≤5 min MP4 (uploaded file, not a YouTube link unless the form says otherwise), competition account ID, up to 5 tagged social links.
- Submitted Friday afternoon BST, not Friday evening.

## Functional Requirements

**FR-1** Locked universe: SPY, QQQ, IWM only.

**FR-2** Locked structure: put or call credit spread. Iron condors out of scope.

**FR-3** Locked bands: DTE 7–21; short delta 0.20–0.30; long delta 0.10–0.15; ≤2% NAV risk per structure; max 3 open structures; max 1–2 per underlying.

**FR-4** Regime gate in `strategy/regime.py` is deterministic **IV/RV** (ATM IV / 20-day annualized RV) plus a simple breakout flag. Not IV rank. Not an LLM call.

**FR-4b** Separate `OrderStatus` and `StructureStatus`. Orders: INTENT → SUBMITTING → WORKING → PARTIALLY_FILLED → FILLED | CANCELED | REJECTED | EXPIRED | NEEDS_REVIEW. Structures: PENDING_ENTRY → OPEN → CLOSING → CLOSED | NEEDS_REVIEW. A canceled partial entry leaves an OPEN structure.

**FR-4c** Reconcile broker orders; cancel stale entries; atomic multi-leg close or fail closed; take profit / stop / regime-reversal / halt-flatten; recover intents after restart.

**FR-5** Proposer (Featherless) emits a pydantic `TradeProposal`. Parse-and-retry ≤3 times; hard-fail closed (no trade) if still invalid.

**FR-6** Critic emits one-paragraph `CriticNote` (“Challenge this trade” + invalidation conditions). Advisory only.

**FR-7** `risk/engine.py` independently re-validates every limit. Approve | Veto(reason).

**FR-8** `execution/executor.py` is the only caller of `place_option_order`. Kill switch, engine, and account guard must all pass. Guard checks paper mode, `EXPECTED_ACCOUNT_ID`, role, and `COMPETE_ENABLED`.

**FR-9** `execution/alpaca_py_fallback.py` submits MLEG via `alpaca-py` if MCP order schema is unusable.

**FR-10** Scheduler sleeps when `get_clock` says closed. ~20–30 min cycle per candidate. ~5 min snapshot + halt check. EOD expiry sweep (close anything inside 2 trading days).

**FR-11** MCP server runs as a supervised local stdio subprocess with auto-restart.

**FR-12** Day-1 `tools/schema_introspect.py` dumps real MCP schemas before any order-construction code is trusted.

**FR-13** CLI wrapper for account/positions/ad hoc ops.

**FR-14** SQLite + JSONL log every cycle (traded or not).

**FR-15** Streamlit desk: header, curve, positions, history, transcript, activity, STOP, run-now, persistent PAPER TRADING banner.

**FR-16** `scripts/setup_check.py`, `run_once.py`, `replay_demo.py`.

**FR-17** Master kill switch as a DB/file flag. Halt or STOP **flattens** open structures, then blocks new orders.

**FR-18** 60–90 min cooldown per underlying.

**FR-19** Idempotent client order IDs so a retry cannot double-submit.

**FR-20** Social calendar: 5 posts (architecture, rejected memo, setback, demo clip, results), tagging lablab + Alpaca.

## Non-Functional Requirements

**NFR-1** Paper trading only. `ALPACA_PAPER_TRADE=true`. No live keys in the repo.

**NFR-2** Secrets only in `.env` (gitignored). `.env.example` has names only.

**NFR-3** Risk and regime tests run with `pytest` and zero network.

**NFR-4** Unattended MCP process must survive multi-hour market sessions (supervisor + reconnect).

**NFR-5** Featherless is the demoed proposer (partner prize). Claude Sonnet is a local debug fallback only.

**NFR-6** Solo-buildable. Streamlit, not Next.js.

**NFR-7** Reproducible: `setup_check.py` passes on a clean checkout with env vars set.

**NFR-8** Do not claim paper P&L equals live performance.

## Success Criteria

**Sunday 30 Aug (market closed)**
- [ ] Sandbox + competition paper accounts exist; Level 3 verified on both; competition starts at $100k.
- [ ] MCP `get_account_info` and CLI account/positions work on sandbox.
- [ ] Real `place_option_order` / chain / snapshot schemas dumped.
- [ ] Featherless smoke call + `TradeProposal` parse+retry works.
- [ ] Risk + regime unit tests pass.
- [ ] Critic can reject a bad fixture; a good fixture produces a sandbox multi-leg order **or** a logged MCP/fallback attempt with a clear error.
- [ ] Social post #1 published.

**Monday 31 Aug**
- [ ] Scheduler pointed at competition keys before 9:30 ET.
- [ ] ≥1 full cycle on the judged account (trade or documented veto).
- [ ] If regime is rich: 1–2 small credit spreads on SPY/QQQ.
- [ ] Social post #2 includes a rejected proposal.

**Thursday 3 Sep**
- [ ] Code frozen, hosted demo up, write-up/slides/video draft done, no leaked keys.

**Friday 4 Sep**
- [ ] Submission in before ~15:00 BST. Competition account shows options activity. All required fields filled.

**Podium bar (not the finish line):** real vetoes visible, P&L small-positive or flat with bounded DD, 90-second demo story is obvious.

## Constraints & Assumptions

- Deadline: Fri 4 Sep 2026, 21:00 BST / 20:00 UTC. Submit Friday afternoon BST.
- Live sessions: Mon 31 Aug – Fri 4 Sep. Friday has no gap between the close and the deadline — do not wait for Friday P&L.
- Solo build. Python + Streamlit + alpaca-py + official `alpaca-mcp-server` + official `alpaca` CLI.
- Paper Level 3 is likely default; **verify**, do not assume.
- `place_option_order` JSON schema is not reliable in prose docs — introspect first.
- Featherless structured output is flaky — parse+retry, fail closed.
- Two accounts: sandbox vs judged $100k.
- Strategy spec is locked mid-week. No NVDA/TSLA, no 0DTE, no human-required approval on the live loop.
- Deadline, video format, and prize copy stay provisional until demo-submission/001 closes.

## Out of Scope

- Live-money trading
- Next.js / FastAPI / shadcn rewrite
- Three-model debate on a 20-minute timer
- Human click required before every order
- Single-stock directional plays
- Custom model training, RAG, backtest gym
- Crypto as a primary book
- Rolling / assignment management beyond the 2-day expiry sweep
- Multi-broker support
- Voice control
- Expanding the universe after Monday
- Iron condors
- Custom ThetaGate MCP server
- Claiming Alpaca MCP can halt us or explain our SQLite log
- IV-rank history store

## Dependencies

- Alpaca paper accounts (sandbox + competition), API keys, Level 3 options
- `alpacahq/alpaca-mcp-server`, official Alpaca CLI, `alpaca-py`
- Featherless API credits ($25 participant credits)
- Optional Anthropic key for local debug only
- lablab.ai enrollment, Discord, submission form fields (verify video/one-pager/slides Day 1)
- Hosting: Streamlit Cloud or Railway
- Source of truth for product: `plan.md`

## Epic Map (build order)

```
demo-submission/001 (P0 form)
        ↓
project-foundation
        ↓
alpaca-stack (connect + schema; no supervisor)
        ↓
risk-gates (IV/RV + engine + mapper)
        ↓
minimal proposer + executor dry-run
        ↓
sandbox run_once
        ↓
order lifecycle + account guard
        ↓
competition activation
        ↓
operator-desk + replay
        ↓
wave 2: critic, CLI polish, social, video
```

Sunday critical path: foundation → (stack ∥ risk ∥ schemas) → sandbox `run_once` fill.  
Monday critical path: execution-loop on the competition account before the open.  
Dashboard and write-up can start on stubs as soon as SQLite exists.

## Locked numbers

| Knob | Value |
|---|---|
| Universe | SPY, QQQ, IWM |
| First structure | Credit spread (put first) |
| DTE | 7–21 |
| Short / long delta | 0.20–0.30 / 0.10–0.15 |
| Risk per structure | ≤2% of $100k |
| Open structures | ≤3 total, ≤2 per underlying |
| Daily / total halt | −3% SOD / −8% start |
| Expiry sweep | Close if ≤2 trading days left |
| Cooldown | 60–90 min / underlying |
| Cycle cadence | 20–30 min / name |
| Snapshot loop | ~5 min |
