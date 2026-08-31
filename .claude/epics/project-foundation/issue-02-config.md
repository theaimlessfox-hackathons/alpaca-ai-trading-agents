---
name: Config and secrets
type: issue
epic: project-foundation
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T19:53:06Z
github: (will be set on sync)
agent: Senior Developer
subissues: ["005", "006", "007", "008", "009"]
progress: 0%
---
# Issue: Config and secrets

**Epic:** `project-foundation`  
**Agent:** Senior Developer  
**Subissues:** 005, 006, 007, 008, 009

## Subissues

  - [ ] `005` Add .env.example two-account slots (seq, XS, 0.3h)
  - [x] `006` Implement settings.py locked knobs (seq, S, 0.8h)
  - [x] `007` Smoke-import settings (seq, XS, 0.2h)
  - [x] `008` Stub setup_check env validation (seq, XS, 0.4h)
  - [x] `009` OrderStatus vs StructureStatus (`config/states.py`)

## Done when

- [ ] Settings load; paper defaults true; compete_enabled defaults false
- [ ] `OrderStatus` and `StructureStatus` are separate types; no StructureStatus.CANCELED
