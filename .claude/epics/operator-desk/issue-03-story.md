---
name: Decision story
type: issue
epic: operator-desk
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: Frontend Developer
subissues: ["007", "008", "009", "010", "011"]
progress: 100%
---
# Issue: Decision story

**Epic:** `operator-desk`  
**Agent:** Frontend Developer  
**Subissues:** 007, 008, 009, 010, 011

## Subissues

  - [x] `007` Transcript proposal pane (seq, S, 0.7h) -- was reading `row["thesis"]`, a key that never existed on a real cycle row; now parses it out of `proposal_json`
  - [x] `008` Challenge and verdict pane (seq, S, 0.7h) -- same fix, was reading `row["critic"]` (never existed) instead of the new `critic_json` column; critic is now actually wired into the live cycle too (see agent-cycle epic), so there's real content to show
  - [x] `009` Activity feed (seq, XS, 0.4h)
  - [x] `010` **Cut, correctly not built** -- per instruction, run-cycle-now is out of scope; `scheduler --once` covers the same need
  - [x] `011` Replay toggle (seq, S, 0.8h)

## Done when

- [x] Every subissue above is closed
