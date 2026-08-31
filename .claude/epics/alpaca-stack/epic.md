---
name: alpaca-stack
status: completed
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T22:00:00Z
progress: 100%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

# Epic: alpaca-stack

## Overview

Wire official Alpaca MCP (supervised stdio) and the official CLI. Dump real tool schemas before anyone writes order payloads. Expose read-only research/account wrappers. Expand `setup_check.py` to prove account, clock, options level, MCP, CLI, and a Featherless ping.

**Blocked by:** project-foundation.  
**Unblocks:** execution-loop order path; structures payload shape.

## Architecture Decisions

- Talk to `alpaca-mcp-server` via local stdio + the `mcp` Python client. Do not use Anthropic's remote MCP connector (it would let the model fire tools server-side).
- Supervisor restarts a hung/dead MCP process.
- `place_option_order` is wrapped only in `execution/` (later epic). This epic must not give that tool to any agent-facing module.
- CLI is a thin subprocess wrapper for demo/cron, not a second trading brain.
- Schema dump is a one-off script; commit the dump under `docs/mcp-schemas/` (no secrets).

## Technical Approach

### Frontend Components

None.

### Backend Services

- `mcp_integration/server_manager.py`
- `mcp_integration/client.py`
- `tools/schema_introspect.py`
- `tools/research_tools.py` (chain, snapshot, bars, news, clock)
- `tools/account_tools.py` (account, positions, portfolio history)
- `cli_integration/ops.py`
- `scripts/setup_check.py` (complete)

### Infrastructure

`uvx alpaca-mcp-server` or installed package; official `alpaca` CLI; sandbox API keys.

## Implementation Strategy

001–002 sequential (manager then client). 003–005 parallel after client exists. 006 last.

## Task Breakdown Preview

1. MCP server supervisor
2. Async MCP client (`connect`, `call_tool`, `list_tools`)
3. Schema introspect + committed dump
4. Read-only research tools
5. Read-only account tools
6. CLI ops wrapper
7. Full `setup_check.py` (both accounts if keys present)

## Dependencies

- project-foundation
- Sandbox (and later competition) API keys
- Network to Alpaca paper + Featherless

## Success Criteria (Technical)

- `setup_check.py` prints account equity, clock, options level, MCP tool count, CLI account/positions, and a Featherless key-presence check. **Done and live-verified** (Aug 30, sandbox account PA3KII0I2OJ1: equity $100,000, options_level 3, 72 MCP tools, clock reachable). This didn't originally cover account/clock/Featherless at all -- only env validation + a bare MCP ping + CLI account -- fixed as part of closing out this epic rather than leaving the tracker saying "done" when it wasn't.
- `docs/mcp-schemas/place_option_order.json` exists. **Done.**
- No order is placed by this epic except an optional documented tiny cancel-immediately test (prefer none). **Held** -- no orders placed by anything in this epic's scope.
- CLI scope is intentionally just one read (`cli_integration/ops.py:account()`) per the locked "one CLI read" decision -- the "CLI positions" wording above is stale from before that was locked; `account()` satisfies alpaca-stack/008's actual acceptance criteria ("ops.account() or ops.positions()").

## Estimated Effort

4–6 hours. 7 tasks. Parallel after the client lands.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 4
Subissues: 11

- [x] `issue-01-mcp-process` MCP process — MCP Builder (3 subissues, all closed; auto-restart supervisor (003) correctly deferred to wave 2, not built)
- [x] `issue-02-schema-dump` Schema dump — MCP Builder (2 subissues, both closed; live-verified against a real chain pull, see docs/mcp-schemas/SOURCE.md)
- [x] `issue-03-readonly-tools` Read-only tools — MCP Builder (2 subissues, both closed; both now unwrap the security envelope, fixed as part of execution-loop work)
- [x] `issue-04-cli-check` CLI and setup check — MCP Builder (4 subissues, all closed; setup_check.py's account/clock/Featherless checks were the actual gap, now fixed and live-verified)

