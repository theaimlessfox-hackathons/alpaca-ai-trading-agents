---
name: execution-loop
status: completed
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T22:00:00Z
progress: 100%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

# Epic: execution-loop

## Overview

Persist every cycle, place approved multi-leg orders, **run a full order lifecycle** (reconcile, cancel, close, exits, halt-flatten, restart recovery), guard the competition account, and expose `run_once.py`.

**Blocked by:** `alpaca-stack/002`+`005`, `risk-gates/010`+`014`+`011`, `agent-cycle/010`.  
**Unblocks:** operator-desk live data; judged-account activation.

## Architecture Decisions

- Executor is the only module that may call `place_option_order` or `TradingClient.submit_order`.
- Re-run `RiskEngine.validate` + kill-switch check immediately before submit. Do not trust an earlier cycle result.
- Idempotency: hash + persist intent + local DB lookup + Alpaca lookup by client_order_id. Timeouts stay ambiguous until reconcile.
- Close is one atomic multi-leg order or fail closed. Never leg out.
- Close uses the same intent + client_order_id + lock as entries.
- Kill switch **flattens** via `flatten_all`; scheduler only calls it.
- Exits: 40–60% of credit, loss multiple, regime reversal, unfilled timeout. Expiry sweep is backup only.
- Executor refuses live trading, mismatched `EXPECTED_ACCOUNT_ID`, and competition mode without `COMPETE_ENABLED`.
- SQLite is the dashboard source of truth; JSONL is the greppable demo trail.

## Technical Approach

### Frontend Components

None.

### Backend Services

- `storage/db.py`, `storage/logger.py`
- `execution/executor.py`, `execution/alpaca_py_fallback.py`
- `scheduler/market_hours.py`, `scheduler/loop.py`
- `scripts/run_once.py`

### Infrastructure

Sandbox keys Sunday; switch env to competition keys before Monday 9:30 ET.

## Implementation Strategy

storage first (desk can start). executor + fallback parallel. market hours then loop. run_once last.

## Task Breakdown Preview

1. SQLite schema + helpers
2. JSONL logger
3. MCP executor
4. alpaca-py MLEG fallback
5. Market hours
6. Scheduler loop
7. `run_once.py`

## Dependencies

- MCP client, structures, risk engine, kill switch, cycle
- Sandbox account for first fill

## Success Criteria (Technical)

- `run_once.py --symbol SPY` (dry) writes a transcript and never calls place. **Done, live-verified** against the real sandbox account.
- Halt with an open fixture structure calls `close_structure`. **Done.**
- Duplicate client_order_id cannot produce two broker orders in tests. **Done -- and was actually broken until this pass**: the live-submit path recorded no `broker_order_id`, so this guard could never fire for a real order. Fixed in `execution/executor.py`; see `test_live_submit_records_broker_order_id_for_idempotency`.
- Competition keys without `COMPETE_ENABLED` cannot submit. **Done.**

### Found and fixed during closeout (not caught by the original subissue-level tests)

- `execution/broker.py` checked the account guard by comparing `EXPECTED_ACCOUNT_ID` to itself (`assert_can_submit(account_id=s.expected_account_id or None)`) -- a tautology that could never detect a real mismatch. Now resolves the real account via a live `get_account_info()` call (`execution/account_guard.py:resolve_account_id`) and fails closed if it can't.
- Nothing created a `structures`/`orders` row for a live entry -- `close_structure`/`flatten_all`/`open_structures` had nothing to act on for a real position. `execution/executor.py`'s live path now creates both and persists the entry payload (`orders.payload_json`, new column) so a later close/flatten doesn't depend on a caller's in-memory state.
- `execution/flatten.py:flatten_all` silently skipped any structure it didn't have a payload for. Now falls back to the persisted payload and logs (and counts) genuine skips instead of returning a silently-incomplete count.
- `tools/account_tools.py` never unwrapped the MCP response envelope (same bug `research_tools.py` had) -- fixed.

## Estimated Effort

6–8 hours. 7 tasks.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 5
Subissues: 21

- [x] `issue-01-ledger` Ledger (3) -- gained a `payload_json` column on `orders` (with an additive migration in `create_all`) so entry payloads survive for later close/flatten
- [x] `issue-02-orders` Order path (4) -- broker_order_id recording and structure/order creation were the real gaps, now fixed
- [x] `issue-03-run` Scheduler and run_once (5) -- `equity_history` gained a `ts` column (also migrated) so daily P&L is computable; scheduler.loop now uses storage.db.insert_equity instead of untimestamped raw SQL
- [x] `issue-04-order-lifecycle` Reconcile / close / exits / flatten / recover (8) -- flatten_all now falls back to the persisted entry payload and logs genuine skips
- [x] `issue-05-account-guard` Competition invariants (1) -- was a tautological no-op check in the live path; now resolves and verifies the real account

