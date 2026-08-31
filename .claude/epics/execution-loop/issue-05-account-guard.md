---
name: Competition account guard
type: issue
epic: execution-loop
status: closed
created: 2026-08-30T20:30:00Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: Backend Architect
subissues: ["021"]
progress: 100%
---
# Issue: Competition account guard

**Epic:** `execution-loop`  
**Agent:** Backend Architect  
**Subissues:** 021

## Found broken during closeout, now fixed

The "wrong account id" check was a no-op in the real submit path: `execution/broker.py` compared `EXPECTED_ACCOUNT_ID` to itself instead of to a real resolved account, and `execution/executor.py`'s pre-check silently skipped whenever no `account_id` was supplied (which nothing did). Now `execution/account_guard.py:resolve_account_id` fetches the real account via a live `get_account_info()` call, and `assert_can_submit` fails closed (raises) if `EXPECTED_ACCOUNT_ID` is configured but no real id could be resolved, rather than silently passing.

## Done when

- [x] Executor refuses live trading, wrong account id, and competition mode without COMPETE_ENABLED
- [x] Sandbox fills cannot run on the competition key pair (role check + COMPETE_ENABLED gate)
