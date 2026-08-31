---
name: CLI and setup check
type: issue
epic: alpaca-stack
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: MCP Builder
subissues: ["008", "009", "010", "011"]
progress: 100%
---
# Issue: CLI and setup check

**Epic:** `alpaca-stack`  
**Agent:** MCP Builder  
**Subissues:** 008, 009, 010, 011

## Subissues

  - [x] `008` CLI account command (seq, S, 0.5h)
  - [x] `009` **Cut, correctly not built** -- 009.md's actual title is "(cut) extra CLI commands"; the locked scope is one CLI read via `account()`, folded into 008. The line above ("CLI positions command") is stale wording from before that cut was decided; do not build a positions() CLI wrapper.
  - [x] `010` setup_check live pings (seq, S, 0.7h) -- was missing account equity/options-level/clock/Featherless checks despite being named in the epic's success criteria; fixed and live-verified against the real sandbox account (equity $100,000, options_level 3, 72 tools)
  - [x] `011` Print both account IDs (seq, XS, 0.3h)

## Done when

- [x] Every subissue above is closed
