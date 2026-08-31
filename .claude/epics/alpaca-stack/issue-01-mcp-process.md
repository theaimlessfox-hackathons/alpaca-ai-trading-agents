---
name: MCP process
type: issue
epic: alpaca-stack
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: MCP Builder
subissues: ["001", "002", "003"]
progress: 100%
---
# Issue: MCP process

**Epic:** `alpaca-stack`  
**Agent:** MCP Builder  
**Subissues:** 001, 002, 003

## Subissues

  - [x] `001` MCP server supervisor (parallel, S, 1.2h) -- basic start/kill only, by design; auto-restart is 003
  - [x] `002` Async MCP client core (seq, S, 1.0h)
  - [x] `003` Client timeouts and close (seq, XS, 0.5h) -- note: this subissue's actual title in 003.md is "MCP auto-restart supervisor (wave 2)" and it is closed via its own AC (not on the Sunday path, correctly not built) -- do not confuse with the timeout/close AC this parent issue's line originally implied

## Done when

- [x] Every subissue above is closed
