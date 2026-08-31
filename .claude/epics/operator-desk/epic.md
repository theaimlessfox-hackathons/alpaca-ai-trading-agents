---
name: operator-desk
status: completed
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T22:00:00Z
progress: 100%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

# Epic: operator-desk

## Overview

Streamlit desk that tells GPT's story on Grok's book: event → evidence → proposal → challenge → risk verdict → execution. Rejected trades are first-class. Approval is a demo overlay, not a live gate. MCP-chat is documented as a second window on the same server.

**Blocked by:** storage schema (execution-loop/001). UI shells can start on fixtures immediately after foundation.

## Architecture Decisions

- Streamlit only. No Next.js.
- Read-only against SQLite except STOP flag and “run cycle now” (writes kill-switch / enqueues one cycle).
- Persistent PAPER TRADING banner.
- Replay mode reads a saved snapshot; does not hit live Alpaca if `--replay` is set.
- Optional approve button appears only in demo/replay. Production scheduler ignores it.

## Technical Approach

### Frontend Components

- `dashboard/app.py`
- `dashboard/components.py` (stat tiles, curve, tables, transcript, activity)
- Seeded fixture JSON for empty-state and replay

### Backend Services

Reads `storage/db.py`; writes kill-switch.

### Infrastructure

Streamlit Cloud or Railway for the hosted demo.

## Implementation Strategy

Shell + header first. Remaining panels are parallel (different component functions). Polish last.

## Task Breakdown Preview

1. App shell, paper banner, header metrics, STOP
2. Equity curve + positions
3. Trade history
4. Transcript viewer (proposal, critic, verdict, evidence)
5. Activity feed + run-cycle-now
6. Replay toggle + fixture load
7. Hosting + README run instructions

## Dependencies

- `storage/db.py` (or fixtures)
- kill switch flag

## Success Criteria (Technical)

- A judge can follow one rejected and one filled cycle without reading code. **Fixed during closeout**: the transcript panel was reading `row["thesis"]`/`row["critic"]`, keys that never existed on the actual cycle-row shape (`storage.db.recent_cycles()` only ever returns `id/verdict/reason/proposal_json/critic_json`) -- it would have shown raw JSON or nothing. Now parses `proposal_json` for the thesis and `critic_json` for the critic's rebuttal.
- STOP flips the flag the executor already honors. **Done.** (The scheduler's snapshot/halt loop is what turns that flag into an actual flatten, on its next ~5-min check -- the dashboard itself only needs to write the flag, matching this epic's own "writes kill-switch" scope.)
- Replay works with Alpaca keys unset. **Done** -- `fixtures/replay_spy.json` exists and the toggle reads it without touching MCP.

### Also found and fixed during closeout

- Header tiles (`tiles(100_000, 0, 0, killed)`) were hardcoded constants regardless of real account state -- equity and daily P&L never moved no matter what the scheduler was doing, and `open_n` disagreed with the real count shown a few lines later in the positions table. Now reads `storage.db.recent_equity()`/`daily_pnl()` (new helpers; `equity_history` gained a `ts` column so "daily" is actually computable) and the same `structs` count used in the positions table.

## Estimated Effort

5–7 hours. 7 tasks, highly parallel after the shell.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 4
Subissues: 13

- [x] `issue-01-shell` Desk shell — Frontend Developer (3 subissues)
- [x] `issue-02-book` Book views — Frontend Developer (3 subissues; equity curve now reads real `equity_history`, not a hardcoded empty list)
- [x] `issue-03-story` Decision story — Frontend Developer (5 subissues; "run cycle now" correctly cut, not built; transcript field mismatch fixed)
- [x] `issue-04-host` Host and runbook — Frontend Developer (2 subissues; README + railway.toml both exist)

