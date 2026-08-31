---
name: Replay and video
type: issue
epic: demo-submission
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: Technical Writer
subissues: ["006", "007"]
progress: 100%
---
# Issue: Replay and video

**Epic:** `demo-submission`  
**Agent:** Technical Writer  
**Subissues:** 006, 007

## Subissues

  - [x] `006` VIDEO.md timed script (parallel, S, 0.8h) -- fixed an understated MCP-chat claim ("buying power only" -> account/positions/orders/market data)
  - [x] `007` Note replay_demo.py contract (parallel, XS, 0.3h) -- `scripts/replay_demo.py` exists and is referenced as the live-data-dies fallback

## Done when

- [x] Every subissue above is closed

## Still needs a human, not code

Recording the actual MP4 is outside what this repo can produce. Recommend recording a **replay of an already-completed real cycle** (via `scripts/replay_demo.py`) rather than gambling on a live fill happening during the exact recording window.
