---
name: Credit spread mapper
type: issue
epic: risk-gates
status: closed
created: 2026-08-30T19:53:06Z
updated: 2026-08-30T19:53:06Z
github: (will be set on sync)
agent: Backend Architect
subissues: ["014"]
progress: 0%
---
# Issue: Credit spread mapper

**Epic:** `risk-gates`  
**Agent:** Backend Architect  
**Subissues:** 014

## Subissues

  - [ ] `014` structures.py + tests (parallel, M, 1.5h)

## Done when

- [ ] Every subissue above is closed
- [ ] Mapper is blocked until `alpaca-stack/005` (real place_option_order schema)
- [ ] pytest builds a 2-leg credit spread and rejects a condor
- [ ] Payload keys match the dumped schema
