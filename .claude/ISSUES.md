---
name: thetagate-issues
updated: 2026-08-30T20:30:00Z
---

# ThetaGate — epics, issues, subissues

Canonical ids: `epic/NNN` (example: `risk-gates/014`). Never depend on a bare `001`.

**7 epics · 28 issues · 88 subissues.**

Leaf `Hours:` sum (~84h) is **not** calendar time. Wave 2, cut, and parallel-owned work overlap; do not add the leaves.  
Credible **solo wall-clock** for a shippable week: **65–80h** (wave 0–1 implementation + install + paper debug + live watch + record + submit). Wave 2 is extra if time exists.

## Build order (do this, not epic-folder order)

```
P0  demo-submission/001     form fields (blocks hard-coded deadline/format)
 0  project-foundation
 0  alpaca-stack 001–002, 004–008, 010   (no supervisor, one CLI read)
 0  risk-gates IV/RV + engine + 014 mapper (needs alpaca-stack/005)
 0  agent-cycle 001,003,004,006,008,010  (no critic)
 0  execution-loop dry-run 004 + 007 + 012
 1  execution-loop 013–021 lifecycle + account guard
 1  one sandbox run_once --live
 1  COMPETE_ENABLED + expected account id
 1  operator-desk shell + transcript + replay
 2  critic, MCP supervisor, extra CLI, run-cycle-now, social, video
```

## Cuts (do not pull onto the Sunday path)

| Item | Status |
|---|---|
| Iron condors | out of scope |
| CLI beyond one read | `alpaca-stack/009` cut |
| Critic LLM | wave 2 (`agent-cycle/002,005,009`) |
| MCP auto-restart | wave 2 (`alpaca-stack/003`) |
| Run cycle now | cut (`operator-desk/010`) |
| Custom ThetaGate MCP | will not build |
| IV-rank history | will not build — use IV/RV |
| Social as a blocker | wave 2 |

## Alpaca MCP chat — allowed claims

Official Alpaca MCP: account, positions, orders, market data.  
Not supported: explain last ThetaGate trade, halt scheduler, show risk budget. Those live on Streamlit / `logs/KILL`.

---

## Epic: `demo-submission` (P0 first)

### Submission form (`issue-01-form`)
- [ ] `001` **P0** verify lablab form fields
- [ ] `002` SUBMIT checklist (wave 2)

### Write-up / demo / social — wave 2
- [ ] `003`–`009` docs, video, social (not code-critical)

**Issue done when:** live form is transcribed; CLAUDE.md/plan.md match the form.

---

## Epic: `project-foundation`

### Repo bootstrap (`issue-01-repo-bootstrap`)
- [ ] `001` CLAUDE.md (provisional deadline)
- [ ] `002` package tree
- [ ] `003` gitignore
- [ ] `004` requirements.txt

### Config (`issue-02-config`)
- [ ] `005` .env.example including EXPECTED_ACCOUNT_ID, COMPETE_ENABLED
- [x] `006` settings.py + iv_rv knobs
- [x] `007` smoke import
- [x] `008` setup_check env
- [x] `009` **OrderStatus ≠ StructureStatus** (`config/states.py`)

**Issue done when:** `get_settings()` loads; paper defaults true; compete_enabled defaults false; dual status enums exist.

---

## Epic: `alpaca-stack`

### MCP process
- [ ] `001` start stdio process (no supervisor)
- [ ] `002` async client
- [ ] `003` auto-restart (wave 2)

### Schema dump
- [ ] `004` introspect script
- [ ] `005` place_option_order.json committed

### Read-only tools
- [ ] `006` research wrappers (bars + chain)
- [ ] `007` account wrappers

### CLI + check
- [ ] `008` one CLI read
- [ ] `009` cut
- [ ] `010` setup_check pings
- [ ] `011` print account IDs

**Issue done when:** `list_tools()` works; schema dump exists; one CLI read works; zero orders placed.

---

## Epic: `risk-gates`

### Regime (IV/RV, not IV rank)
- [ ] `001` types
- [ ] `002` IV/RV + breakout
- [ ] `003` tests

### Universe
- [ ] `004`–`005` SPY/QQQ/IWM lock

### Engine (sequential, same file)
- [ ] `006`–`010` verdict, rules, recompute loss, tests

### Kill switch
- [ ] `011`–`013` flag, halts, cooldown

### Mapper
- [ ] `014` **depends_on alpaca-stack/005**

**Issue done when:** offline pytest green for regime, engine (every veto), structures; mapper keys match dumped schema.

---

## Epic: `agent-cycle`

### Contract
- [ ] `001` TradeProposal (then `002` CriticNote wave 2, same file)
- [ ] `003` parse_and_retry fail-closed

### Prompts / LLM
- [ ] `004` proposer prompt
- [ ] `005` critic prompt (wave 2)
- [ ] `006`–`007` Featherless client + smoke

### Agents
- [ ] `008` run_proposer
- [ ] `009` run_critic (wave 2, after execution-loop/012)
- [ ] `010` cycle, no execution import
- [ ] `011` stand-down skips LLM

**Issue done when:** invalid JSON → no trade; stand-down skips LLM; cycle does not import execution.

---

## Epic: `execution-loop`

### Ledger
- [ ] `001`–`003` sqlite + helpers + jsonl (`intents` table required)

### Order path
- [ ] `004` dry-run **depends_on** alpaca-stack/002, risk-gates/010, risk-gates/011, risk-gates/014
- [ ] `005` live MCP (wave 1, after 007 + 021)
- [ ] `006` alpaca-py fallback (wave 1)
- [ ] `007` intent + DB + broker idempotency

### Run
- [ ] `008` market hours
- [ ] `009` scheduler **depends_on** agent-cycle/010, alpaca-stack/007, risk-gates/010
- [ ] `010` snapshot + halt loop (calls flatten)
- [ ] `011` expiry sweep (wave 2 backup)
- [ ] `012` run_once dry-run

### Order lifecycle
Two machines (defined in foundation `009`):

- **OrderStatus:** INTENT → SUBMITTING → WORKING → PARTIALLY_FILLED → FILLED | CANCELED | REJECTED | EXPIRED | NEEDS_REVIEW
- **StructureStatus:** PENDING_ENTRY → OPEN → CLOSING → CLOSED | NEEDS_REVIEW

Canceling a partial entry ⇒ order CANCELED, structure still OPEN (`014`).

**File ownership is the four-file split. Do not create `execution/exits.py`.**

| Task | File only |
|---|---|
| 013 / 014 / 017 | `execution/reconcile.py` |
| 015 | `execution/cancel.py` |
| 016 | `execution/close.py` |
| 018 | `execution/exit_policy.py` |
| 019 | `execution/flatten.py` |
| 010 | `scheduler/loop.py` |

Order: 015 → 016 → 018 → 019 → 010.

- [ ] `013` reconcile status
- [ ] `014` partial fills
- [ ] `015` cancel stale entries (`execution/cancel.py`)
- [ ] `016` **atomic** close + close intent/lock (`execution/close.py`) — no per-leg close
- [ ] `017` rejected/expired
- [ ] `018` exit policy evaluate only (`execution/exit_policy.py`)
- [ ] `019` `flatten_all` (`execution/flatten.py`) — does not edit scheduler
- [ ] `020` restart recovery

### Account guard (NEW)
- [ ] `021` paper + expected id + role + COMPETE_ENABLED

**Issue done when:** dry-run cycle logs a veto; live sandbox cannot double-submit on timeout; halt flattens; wrong account id cannot submit.

---

## Epic: `operator-desk`

Sequential on `dashboard/app.py` / `components.py`.

- [ ] `001`–`003` shell, tiles, STOP (STOP must flatten via 019)
- [ ] `004`–`006` curve, positions, history
- [ ] `007` transcript
- [ ] `008` critic pane (wave 2)
- [ ] `009` activity
- [ ] `010` cut run-now
- [ ] `011` replay offline
- [ ] `012`–`013` README + host

**Issue done when:** reject + fill fixtures render; replay works with keys unset; STOP sets kill flag.

---

Same-file rule: if two subissues list the same path, they are sequential (`parallel: false`) and `conflicts_with` each other. Do not start both.
