---
name: agent-cycle
status: in-progress
created: 2026-08-30T19:10:48Z
updated: 2026-08-30T22:00:00Z
progress: 73%
prd: .claude/prds/thetagate.md
github: (will be set on sync)
---

# Epic: agent-cycle

## Overview

Featherless proposer + short critic + parse/retry + one-cycle orchestrator. Models never see order tools. Output is a `TradeProposal` + `CriticNote` for the risk engine and the dashboard transcript.

**Blocked by:** project-foundation. Happier after risk-gates schemas/limits exist.  
**Unblocks:** execution-loop cycle wiring; operator-desk transcript shape.

## Architecture Decisions

- Featherless is the demoed model (partner prize). OpenAI-compatible client, confirmed live.
- **Revised from the original plan**: Claude Sonnet is a live runtime failover, not an offline-only debug path. `agents/llm.py:chat()` tries Featherless first and fails over to Claude (when `USE_ANTHROPIC_FALLBACK=true` and a key is set) on a call error or a response that isn't even syntactically valid JSON, before `parse_and_retry`'s own retry loop gets involved. This closes a real reliability gap: a single-vendor outage no longer has to fail the whole cycle closed if a second provider is configured.
- Parse+retry ≤3; fail closed.
- Critic is one paragraph, no tools, advisory. **Still wave 2 (002/005/009), not built yet.**
- Cycle: candidate → regime (skip if stand-down) → **chain slice (skip if no viable structure)** → proposer → critic → return bundle. It does **not** call the executor.
- **Added beyond the original scope, and now the load-bearing part**: `run_cycle` fetches and slices the real option chain (`strategy/chain.py`) before ever calling the proposer, and passes `short_candidates`/`long_candidates` into its context. The proposer chooses from real, currently-quoted contracts; it does not invent strikes. This was added after live testing showed `risk/engine.py`'s numeric gates only ever checked the proposer's self-reported numbers with nothing to cross-check them against -- see `docs/mcp-schemas/SOURCE.md` and `CLAUDE.md`'s "Confirmed live" section for what live testing found (no greeks/IV on this feed, a Black-Scholes fallback in `strategy/blackscholes.py`, an undocumented response envelope, OCC symbol formatting).

## Technical Approach

### Frontend Components

None.

### Backend Services

- `agents/schemas.py`
- `agents/prompts.py`
- `agents/llm.py` (Featherless client + retry)
- `agents/proposer.py`
- `agents/critic.py`
- `agents/cycle.py`

### Infrastructure

`FEATHERLESS_API_KEY`; optional `ANTHROPIC_API_KEY`.

## Implementation Strategy

schemas + prompts parallel. llm client next. proposer and critic parallel. cycle last.

## Task Breakdown Preview

1. Pydantic schemas + parse/retry helper
2. Prompts (proposer, critic)
3. Featherless client + smoke
4. Proposer
5. Critic
6. Cycle orchestrator (no orders)

## Dependencies

- settings
- research tool wrappers (can mock in unit tests)
- regime function (can mock)
- `strategy/chain.py` (chain slicer) and `strategy/blackscholes.py` (delta/IV fallback) -- not in the original plan, added after live testing showed they were required, not optional

## Success Criteria (Technical)

- Invalid JSON is retried then becomes a no-trade. **Done.**
- Valid fixture proposal parses to `TradeProposal`. **Done.**
- Critic returns `CriticNote` with invalidation conditions. **Not built -- wave 2.**
- `cycle.py` on a stand-down regime does not call the LLM. **Done**, and extended: it also does not call the LLM when the chain slice has no viable short+long pair (`test_no_viable_candidates_skips_llm`).
- **Added:** `fetch_and_slice_chain("SPY")` proven live against the real sandbox account -- returns real candidates with sane deltas, not just passing offline tests. `scripts/run_once.py --symbol SPY` (no longer fixture-only by default) runs the full real pipeline end to end.
- **Still open:** no live Featherless (or Claude) chat call has actually succeeded yet -- neither `FEATHERLESS_API_KEY` nor `ANTHROPIC_API_KEY` is set in `.env`. Everything up to that boundary is real and tested; the LLM call itself is the one piece nobody has watched succeed.

## Estimated Effort

4–6 hours. 6 tasks.

## Tasks Created

See `issues.md` for issue → subissue map.

Parent issues: 4
Subissues: 11

- [x] `issue-01-contract` Proposal contract — AI Engineer (3 subissues: 001, 003 closed; 002 CriticNote is wave 2, open)
- [ ] `issue-02-prompts` Prompts — AI Engineer (2 subissues: 004 closed; 005 critic prompt is wave 2, open)
- [x] `issue-03-llm` Featherless client — AI Engineer (2 subissues, both closed; failover to Claude added beyond original scope)
- [ ] `issue-04-agents` Proposer critic cycle — AI Engineer (4 subissues: 008, 010, 011 closed + extended with chain-slice wiring; 009 run_critic is wave 2, open)

