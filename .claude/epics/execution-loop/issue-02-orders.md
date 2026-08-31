---
name: Order path
type: issue
epic: execution-loop
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: Backend Architect
subissues: ["004", "005", "006", "007"]
progress: 100%
---
# Issue: Order path

**Epic:** `execution-loop`  
**Agent:** Backend Architect  
**Subissues:** 004, 005, 006, 007

## Subissues

  - [x] `004` Executor dry-run (seq, S, 0.8h)
  - [x] `005` Executor MCP live (seq, S, 1.0h) -- was recording no `broker_order_id` and creating no ledger row on a real submit; both fixed
  - [x] `006` alpaca-py MLEG fallback (seq, S, 1.0h)
  - [x] `007` Idempotent client_order_id (seq, XS, 0.4h) -- the hash existed but the actual duplicate-guard was broken until `broker_order_id` was recorded (see 005); now covered by `test_live_submit_records_broker_order_id_for_idempotency`

## Done when

- [x] Every subissue above is closed
