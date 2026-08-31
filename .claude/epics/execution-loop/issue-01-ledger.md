---
name: Ledger
type: issue
epic: execution-loop
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: Backend Architect
subissues: ["001", "002", "003"]
progress: 100%
---
# Issue: Ledger

**Epic:** `execution-loop`  
**Agent:** Backend Architect  
**Subissues:** 001, 002, 003

## Subissues

  - [x] `001` SQLite schema (parallel, S, 0.7h) -- `orders` gained `payload_json`, `equity_history` gained `ts`, `cycles` gained `critic_json`; all three migrated additively in `create_all()` so an existing local DB doesn't break
  - [x] `002` Insert and query helpers (seq, S, 0.6h) -- added `get_entry_payload`, `insert_equity`, `recent_equity`, `daily_pnl`
  - [x] `003` JSONL logger (parallel, XS, 0.4h)

## Done when

- [x] Every subissue above is closed
