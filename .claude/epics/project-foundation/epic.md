---
name: project-foundation
status: completed
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T19:10:48Z
progress: 100%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

# Epic: project-foundation

## Overview

Stand up the repo so every other epic can land files without colliding. Captures the locked spec in `CLAUDE.md`, package layout, settings constants, secrets template, and a setup-check stub.

**Unblocks:** alpaca-stack, risk-gates, agent-cycle.

## Architecture Decisions

- Single Python package layout matching `plan.md` (config, mcp_integration, cli_integration, tools, agents, strategy, risk, execution, scheduler, storage, dashboard, scripts, tests, docs, logs).
- `pydantic-settings` for all knobs. No magic numbers in agents or the executor.
- `.env` gitignored; `.env.example` names only.
- `CLAUDE.md` is the session source of truth; update it when the real `place_option_order` schema is known.

## Technical Approach

### Frontend Components

None.

### Backend Services

Empty modules + `config/settings.py` only.

### Infrastructure

Python 3.10+, venv, `requirements.txt`, pytest.

## Implementation Strategy

Do this first, in one short sequential burst. After 002 the other Sunday epics can start in parallel.

## Task Breakdown Preview

1. `CLAUDE.md` — locked spec, safety invariant, schedule
2. Repo scaffold + gitignore + requirements
3. `.env.example` and documented two-account key slots
4. `config/settings.py` — every risk/strategy constant
5. `scripts/setup_check.py` stub (env presence)

## Dependencies

- None (first epic).
- Needs a writable repo (this one).

## Success Criteria (Technical)

- Fresh clone + copied `.env` is enough to import `config.settings`.
- `CLAUDE.md` states: LLM never gets order tools; two accounts; locked bands; deadline 20:00 UTC 4 Sep.
- No secrets in git.

## Estimated Effort

2–3 hours. 5 tasks, mostly sequential.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 2
Subissues: 9

- [ ] `issue-01-repo-bootstrap` Repo bootstrap — Senior Developer (4 subissues)
- [ ] `issue-02-config` Config, secrets, and dual status enums — Senior Developer (5 subissues)

