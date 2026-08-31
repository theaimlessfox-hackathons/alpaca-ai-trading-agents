---
name: Read-only tools
type: issue
epic: alpaca-stack
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T22:00:00Z
github: (will be set on sync)
agent: MCP Builder
subissues: ["006", "007"]
progress: 100%
---
# Issue: Read-only tools

**Epic:** `alpaca-stack`  
**Agent:** MCP Builder  
**Subissues:** 006, 007

## Subissues

  - [x] `006` Research tool wrappers (seq, S, 0.8h) -- now an explicit allowlist (not a `place_`-prefix denylist), and unwraps the security envelope
  - [x] `007` Account tool wrappers (seq, XS, 0.6h) -- fixed to unwrap the security envelope too (was returning the raw MCP CallToolResult, not parsed JSON, until execution-loop work needed a real account id and caught it)

## Done when

- [x] Every subissue above is closed
