# Issues — execution-loop

See also `issue-04-order-lifecycle.md` (013–020) and `issue-05-account-guard.md` (021).
Canonical deps live on each `NNN.md` as `epic/NNN`.

**Do not add `execution/exits.py`.** Lifecycle code is split:

- `execution/reconcile.py` — 013, 014, 017
- `execution/cancel.py` — 015
- `execution/close.py` — 016
- `execution/exit_policy.py` — 018
- `execution/flatten.py` — 019
- `scheduler/loop.py` — 010 only

## issue-01-ledger — Ledger
Agent: **Backend Architect**

  - [ ] `001` SQLite schema (parallel, S, 0.7h)
  - [ ] `002` Insert and query helpers (seq, S, 0.6h)
  - [ ] `003` JSONL logger (parallel, XS, 0.4h)

## issue-02-orders — Order path
Agent: **Backend Architect**

  - [ ] `004` Executor dry-run (seq, S, 0.8h)
  - [ ] `005` Executor MCP live (seq, S, 1.0h)
  - [ ] `006` alpaca-py MLEG fallback (seq, S, 1.0h)
  - [ ] `007` Idempotent client_order_id (seq, XS, 0.4h)

## issue-03-run — Scheduler and run_once
Agent: **Backend Architect**

  - [ ] `008` market_hours.py (parallel, XS, 0.6h)
  - [ ] `009` Scheduler name cycle (seq, M, 1.0h)
  - [ ] `010` Snapshot and halt loop (seq, S, 0.6h)
  - [ ] `011` Expiry sweep (seq, S, 0.5h)
  - [ ] `012` run_once.py (seq, S, 0.7h)

