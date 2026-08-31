---
name: risk-gates
status: completed
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T19:10:48Z
progress: 100%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

# Epic: risk-gates

## Overview

All deterministic gates: regime (whether to even ask the model), risk engine (whether a proposal may spend), kill switch / daily and total halts / expiry sweep flags, and `structures.py` mapping a `TradeProposal` to an MCP/alpaca-py payload.

**Blocked by:** project-foundation (`settings.py`).  
`structures.py` also needs the schema dump from alpaca-stack.  
**Unblocks:** agent-cycle (can import limits), execution-loop.

## Architecture Decisions

- Pure functions. No I/O in `regime.py` or `engine.py` except reading values passed in.
- Engine does not trust proposer-supplied `est_max_loss`; it recomputes from legs + prices.
- Kill switch is a file/DB flag plus computed daily/total halt. Either one blocks the executor.
- Tests are the highest-ROI code in the repo. No network.

## Technical Approach

### Frontend Components

None.

### Backend Services

- `strategy/regime.py`
- `strategy/signals.py` (SPY/QQQ/IWM only)
- `strategy/structures.py`
- `risk/engine.py`
- `risk/kill_switch.py`
- `tests/test_regime.py`, `tests/test_risk_engine.py`, `tests/test_structures.py`

### Infrastructure

pytest.

## Implementation Strategy

regime, engine, kill_switch, signals in parallel (different files). structures after schema dump. tests land with each module.

## Task Breakdown Preview

1. Regime gate + tests
2. Candidate loop (SPY/QQQ/IWM)
3. Risk engine + tests (every veto reason)
4. Kill switch / halt flags / cooldown bookkeeping
5. Structures mapper + tests (after schema dump)

## Dependencies

- `config/settings.py`
- alpaca-stack schema dump for task 5
- Shared `TradeProposal` type: define a minimal TypedDict/pydantic in `agents/schemas.py` if agent-cycle has not landed; do not block engine tests on Featherless.

## Success Criteria (Technical)

- `pytest tests/test_risk_engine.py tests/test_regime.py tests/test_structures.py` green, offline.
- A fixture that violates any locked band is vetoed.
- A fixture inside all bands is approved.

## Estimated Effort

4–5 hours. 5 tasks, 4 parallel.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 5
Subissues: 14

- [ ] `issue-01-regime` Regime gate — Backend Architect (3 subissues)
- [ ] `issue-02-universe` Universe lock — Backend Architect (2 subissues)
- [ ] `issue-03-engine` Risk engine — Backend Architect (5 subissues)
- [ ] `issue-04-kill-switch` Kill switch and cooldown — Backend Architect (3 subissues)
- [ ] `issue-05-structures` Credit spread mapper — Backend Architect (1 subissues)

