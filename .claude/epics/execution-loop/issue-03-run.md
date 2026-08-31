---
name: Scheduler and run_once
type: issue
epic: execution-loop
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: Backend Architect
subissues: ["008", "009", "010", "011", "012"]
progress: 100%
---
# Issue: Scheduler and run_once

**Epic:** `execution-loop`  
**Agent:** Backend Architect  
**Subissues:** 008, 009, 010, 011, 012

## Subissues

  - [x] `008` market_hours.py (parallel, XS, 0.6h)
  - [x] `009` Scheduler name cycle (seq, M, 1.0h) -- `scheduler/cycle_loop.py`
  - [x] `010` Snapshot and halt loop (seq, S, 0.6h) -- `scheduler/loop.py:snapshot_and_maybe_flatten`; was writing equity_history with no timestamp, now uses `storage.db.insert_equity`
  - [x] `011` Expiry sweep (seq, S, 0.5h) -- `execution/expiry.py:should_sweep`
  - [x] `012` run_once.py (seq, S, 0.7h) -- default (no flags) is the offline fixture path; `--live-data` opts into real bars/chain + regime (still dry-run only); `--veto` forces a universe-veto fixture; `--live` is accepted but live submission isn't wired through this script

## Done when

- [x] Every subissue above is closed
