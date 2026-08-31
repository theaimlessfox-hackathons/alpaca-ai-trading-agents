---
name: thetagate-roster
created: 2026-08-30T19:10:48Z
---

# ThetaGate agent roster

1 PRD · 7 epics · 28 issues · 87 subissues. Map: `.claude/ISSUES.md`.

P0 first: `demo-submission/001`. Then foundation → MCP+schema → risk+mapper → dry-run executor → sandbox cycle → **order lifecycle** → competition guard → desk. Critic/social/supervisor are wave 2.

```
project-foundation ── Senior Developer          Wave 0
        │
        ├─ alpaca-stack ── MCP Builder          Wave 0
        ├─ risk-gates   ── Backend Architect    Wave 0
        ├─ agent-cycle  ── AI Engineer          Wave 0 (001–003 now)
        └─ demo-submission ── Technical Writer  Wave 0 (docs only)
                    │
            execution-loop ── Backend Architect Wave 1
                    │
            operator-desk ── Frontend Developer Wave 1
```

Do not sync to GitHub until you say so.

## File ownership (no overlap)

| Agent | Files |
|---|---|
| Senior Developer | `CLAUDE.md` `.gitignore` `requirements.txt` `.env.example` `config/` `scripts/setup_check.py` `**/__init__.py` |
| MCP Builder | `mcp_integration/` `tools/` `cli_integration/` |
| Backend Architect (gates) | `strategy/` `risk/` `tests/test_regime.py` `tests/test_risk_engine.py` `tests/test_structures.py` |
| AI Engineer | `agents/` |
| Technical Writer | `docs/` except `docs/mcp-schemas/` |
| Backend Architect (loop) | `storage/` `execution/` `scheduler/` `scripts/run_once.py` |
| Frontend Developer | `dashboard/` `fixtures/` |

## Hard rules for every agent

- Paper only. Never commit `.env` or keys.
- LLM never gets `place_option_order`.
- Universe is SPY/QQQ/IWM. First structure is a credit spread.
- Do not touch another agent's files. If blocked, stop and write the blocker in the task file.
