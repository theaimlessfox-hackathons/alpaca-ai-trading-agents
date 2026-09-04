# ThetaGate Agent Guide

This file applies to the entire repository. ThetaGate is an autonomous,
paper-only options desk. Preserve safety and broker-state correctness ahead of
convenience, demo polish, or trade frequency.

## Product boundaries

- Paper trading only. Never add or enable a live-money path.
- Trade defined-risk, two-leg put or call credit spreads only.
- Default universe mode is `discover`: Alpaca most-actives and movers are
  filtered to active, tradable, optionable names. `pinned` mode uses the
  configured `UNIVERSE` (SPY/QQQ/IWM by default).
- DTE: 7–21. Short absolute delta: 0.20–0.30. Long absolute delta: 0.10–0.15.
- Regime gate: ATM IV / 20-day realized volatility. Do not call this IV rank.
- Risk limits: at most 2% NAV max loss per structure, 3 active structures,
  2 per underlying, 3% daily halt, and 8% total halt.
- The LLM proposes only from prefetched candidate contracts. It never receives
  broker order tools and never controls sizing, approval, or execution.

## Non-negotiable execution invariants

- `execution/` is the only package allowed to submit, cancel, or close orders.
- `ALPACA_PAPER_TRADE=false` must remain invalid.
- Every paper submission requires a nonempty `EXPECTED_ACCOUNT_ID` matching the
  account ID resolved from Alpaca immediately before submission.
- Competition credentials never fall back to sandbox credentials.
- Run the deterministic risk engine, kill switch, and account guard immediately
  before broker I/O. Model confidence never overrides a veto.
- Persist structure, order, payload, and intent before broker I/O.
- Treat timeouts, unknown response envelopes, and missing broker IDs as
  ambiguous. Mark `NEEDS_REVIEW`; do not blindly retry.
- Use deterministic client order IDs for entries. Close retries may use a new
  attempt ID only after the prior close is confirmed terminal.
- Close a spread with one atomic multi-leg order. Never leg out.
- Price credit entries as negative net credit and closes as positive net debit.
- Close only reconciled `open_qty`, especially after partial entry fills.
- STOP/halt must cancel every nonterminal entry, reconcile, then flatten filled
  exposure. Report and retry incomplete cancellation or flattening.
- Active risk includes `OPEN`, `CLOSING`, and `NEEDS_REVIEW`; pending entries
  also consume capacity.

## State machines

Keep order state separate from structure state. Update transition tests whenever
changing either machine.

- `OrderStatus`: `INTENT`, `SUBMITTING`, `WORKING`, `PARTIALLY_FILLED`,
  `FILLED`, `CANCEL_REQUESTED`, `CANCELED`, `REJECTED`, `EXPIRED`,
  `NEEDS_REVIEW`.
- `StructureStatus`: `PENDING_ENTRY`, `OPEN`, `CLOSING`, `CLOSED`, `VOID`,
  `NEEDS_REVIEW`.
- A zero-fill canceled/rejected/expired entry makes the structure `VOID`.
- A partially filled then canceled entry remains `OPEN` for its filled quantity.
- A zero-fill canceled/expired close returns the structure to `OPEN`; a partial
  close requires review.

## Architecture

- `agents/`: prompts, model clients, schema parsing, proposal/critic orchestration.
- `strategy/`: universe discovery, chain parsing/slicing, IV/RV regime, pricing,
  and multi-leg payload construction.
- `risk/`: deterministic proposal validation and halt/kill logic.
- `execution/`: account guard, broker boundary, idempotency, order lifecycle,
  reconciliation, closing, exits, and recovery.
- `scheduler/`: autonomous cycle, market-hours gate, equity snapshots, and
  halt/flatten orchestration.
- `storage/`: SQLite schema/ledger plus redacted JSONL event logging.
- `tools/`: read-only Alpaca market/account wrappers. Keep order tools out.
- `dashboard/`: Streamlit observability and STOP/Resume controls.
- `scripts/`: setup checks, one-shot runs, replay, and hosted-service supervisor.
- `docs/mcp-schemas/`: captured Alpaca MCP contracts; treat these as the local
  source of truth for payload fields and sign conventions.

## Alpaca and model integration rules

- Alpaca MCP responses may be wrapped in `{ "_alpaca_mcp_security": ..., "data": ... }`.
  Unwrap centrally with `tools.research_tools.unwrap()`.
- Option snapshots may omit greeks, IV, strike, expiration, and right. The chain
  parser derives contract metadata from the unpadded OCC symbol and may derive
  delta/IV with Black–Scholes inversion.
- Always filter option-chain requests by DTE and a strike window around spot.
- `all_banded` is for ATM-IV calculation only; never send it to the proposer.
- Invalid model output gets at most three schema-validation attempts, then no
  trade. Provider fallback may improve availability but must not bypass binding
  or risk checks.
- Every MCP subprocess must use `mcp_integration.server_manager.mcp_env()` so
  `uvx` uses writable cache/tool directories in hosted environments.

## Working practices

- Read the relevant implementation and tests before editing lifecycle code.
- Preserve unrelated user changes; this worktree may be dirty or mostly
  untracked. Do not reset, discard, or rewrite unrelated files.
- Never print, log, commit, or include `.env` values in test output. Describe
  credentials only as set/missing.
- Keep network and broker calls injectable. Unit tests must not contact Alpaca or
  model providers.
- Prefer small explicit functions and fail-closed return types over broad
  exception swallowing at execution boundaries.
- When behavior changes, update tests and any affected README/config examples.
- Do not hard-code event deadlines or submission requirements without verifying
  the live form; keep provisional facts labeled as provisional.

## Verification

Use the smallest relevant tests while iterating, then run the full offline suite:

```bash
FEATHERLESS_API_KEY= XAI_API_KEY= ANTHROPIC_API_KEY= python3 -m pytest -q
```

Useful operational checks:

```bash
python3 scripts/run_once.py --symbol SPY                 # offline fixture, no order
python3 scripts/run_once.py --symbol SPY --live-data     # live data, dry run
python3 scripts/setup_check.py                           # live connectivity checks
python3 -m scheduler.cycle_loop --once --live            # one paper cycle
python3 -m scheduler.cycle_loop --live                   # continuous paper worker
python3 scripts/start_service.py                         # dashboard + paper worker
```

Commands containing `--live` mean live submission to an Alpaca **paper** account.
Do not run them merely to test code: require explicit user authorization, verify
the expected account, check STOP state, and inspect the ledger first to avoid a
duplicate submission.

## Definition of done

A change is complete only when:

1. The requested behavior is wired into the real scheduler/deployment path, not
   only implemented as an unused helper.
2. Safety invariants and state transitions still hold under timeout, restart,
   partial fill, cancellation, rejection, and duplicate invocation.
3. Targeted regression tests exist and the full offline suite passes.
4. Runtime summaries distinguish a detected trigger from a broker-confirmed
   submission or fill.
5. No secrets, live-money capability, invented contracts, or single-leg close
   path were introduced.
