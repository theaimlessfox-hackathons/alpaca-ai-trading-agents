# ThetaGate

ThetaGate is a paper-only, agent-assisted options credit-spread desk built for the Alpaca AI Trading Agents Hackathon. It discovers liquid optionable names, derives market features in Python, asks an LLM to choose only from pre-filtered contracts, and passes every proposal through deterministic risk and account guards before it can reach Alpaca paper trading.

> **No profit guarantee:** ThetaGate can improve process discipline; it cannot guarantee positive P/L. Options can lose the entire defined risk of a spread. Paper results also omit or simplify several live-market effects, so they should be treated as evidence for further testing—not expected returns.

## What it does

```text
Alpaca activity + recent news
  → persisted start-of-day optionable watchlist
  → option-chain slice
  → ATM IV / realized volatility / breakout regime
  → Featherless proposal from surviving contracts
  → deterministic binding and risk vetoes
  → atomic multi-leg Alpaca paper order
  → reconcile, monitor, exit, and recover
  → SQLite ledger + Streamlit dashboard
```

The model proposes; code controls eligibility, sizing, execution, and exits. The model never receives place, cancel, close, replace, or exercise tools.

Core controls include:

- 7–21 DTE vertical credit spreads with configured short- and long-leg delta bands.
- Quote, IV, geometry, positive-credit, max-loss, capacity, and event-risk checks.
- Paper-account identity verification and no supported live-broker path.
- Atomic multi-leg entry and close orders; ambiguous broker outcomes fail closed.
- Take-profit, stop-loss, regime-reversal, STOP, and kill-switch exits.
- Startup recovery, stale-order cancellation, reconciliation, and idempotent client order IDs.
- A per-symbol cooldown after a filled close to reduce immediate re-entry churn.
- A 10–20-name daily watchlist ranked from Alpaca activity, movement, and news coverage.

When the continuous scheduler is running, it prepares and stores the watchlist
during the 9:00–9:30 ET premarket window. A later startup prepares it on the
first market-open cycle. The first cycle after 12:00 ET refreshes Alpaca
activity and news once for the afternoon; a failed refresh keeps the valid
morning list. Existing positions remain under exit monitoring even when their
symbol is absent from the refreshed entry watchlist.

## Quick start

Python 3.11+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Add only paper credentials and the expected paper account number to `.env`:

```dotenv
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_PAPER_TRADE=true
ALPACA_ACCOUNT_ROLE=sandbox
EXPECTED_ACCOUNT_ID=...

FEATHERLESS_API_KEY=...
FEATHERLESS_MODEL=...
```

Never commit `.env` or set `ALPACA_PAPER_TRADE=false`.

Verify the account, market-data connection, Alpaca tools, CLI, and model before running the scheduler:

```bash
python3 scripts/setup_check.py
FEATHERLESS_API_KEY= XAI_API_KEY= ANTHROPIC_API_KEY= python3 -m pytest -q
```

## Run modes

Start with the modes in this order:

```bash
# Fully offline fixture; no broker order
python3 scripts/run_once.py --symbol SPY

# Real bars, option chain, and model; still no broker order
python3 scripts/run_once.py --symbol SPY --live-data

# One complete scheduler pass; still dry-run
python3 -m scheduler.cycle_loop --once

# One watched paper-order pass
python3 -m scheduler.cycle_loop --once --live

# Continuous paper trading during market hours
python3 -m scheduler.cycle_loop --live

# Dashboard
streamlit run dashboard/app.py
```

In this repository, `--live` means **submit to the verified Alpaca paper account**. It does not enable live-money trading. The safest first order is a watched, one-pass rehearsal; confirm the account ID, order legs, net credit, fill, ledger state, and close path before starting the continuous process.

To stop new entries and trigger flattening while the scheduler is running:

```bash
mkdir -p logs && touch logs/KILL
```

Remove `logs/KILL` only after positions and orders have been reconciled and it is safe to resume.

## Configuration

The main strategy and risk settings live in [config/settings.py](config/settings.py) and can be overridden with environment variables.

| Setting | Default | Purpose |
|---|---:|---|
| `UNIVERSE_MODE` | `discover` | Discover optionable active/moving names, or use `pinned`. |
| `UNIVERSE_SIZE` | `15` | Start-of-day Alpaca activity/news watchlist size (capped at 20). |
| `DTE_MIN` / `DTE_MAX` | `7` / `21` | Allowed days to expiration. |
| `SHORT_DELTA_MIN` / `MAX` | `0.20` / `0.30` | Absolute short-leg delta band. |
| `LONG_DELTA_MIN` / `MAX` | `0.10` / `0.15` | Absolute long-leg delta band. |
| `MAX_LOSS_PCT` | `0.02` | Maximum defined loss for one proposal as a fraction of NAV. |
| `MAX_OPEN_STRUCTURES` | `3` | Portfolio-wide structure cap. |
| `MAX_PER_UNDERLYING` | `2` | Per-symbol structure cap. |
| `BID_ASK_MAX_FRAC` | `0.20` | Maximum relative spread on either leg. |
| `TAKE_PROFIT_FRAC` | `0.50` | Close after capturing 50% of entry credit. |
| `STOP_MULT` | `2.0` | Close when the spread mark reaches 2× entry credit. |
| `REGIME_EXIT_CONFIRMATIONS` | `2` | Consecutive `cheap_iv_rv` readings required before a regime close. |
| `COOLDOWN_MINUTES` | `75` | Block the same symbol after a filled close. |
| `DAILY_HALT_PCT` | `0.03` | Daily equity-drawdown halt. |
| `TOTAL_HALT_PCT` | `0.08` | Total equity-drawdown halt. |

Do not optimize these values from a handful of trades. Change one hypothesis at a time, record the version, and compare it against an untouched holdout period.

## Working toward positive P/L

Positive P/L is an outcome to validate, not a feature flag. Use this loop:

1. **Establish a clean baseline.** Reset only a disposable test ledger or tag a start date; never erase evidence from an active account. Record equity, fills, open risk, and code/config version.
2. **Measure broker fills.** Judge entry credit and close debit from Alpaca fills—not proposal midpoints. Include rejected, canceled, partial, and unresolved orders in the review.
3. **Reduce avoidable churn.** Keep the symbol cooldown enabled, avoid overlapping short strikes, and investigate repeated stop-outs before adding trade frequency.
4. **Segment results.** Compare symbol, put/call side, IV/RV regime, DTE, delta, quote width, time of day, and exit reason. Remove a segment only with enough observations to distinguish signal from noise.
5. **Stress costs.** Recompute results with worse fills and latency assumptions. A strategy that is profitable only at quoted midpoints has not passed.
6. **Use promotion gates.** Require a meaningful sample across different volatility regimes, positive net P/L after cost stress, acceptable drawdown, no unresolved lifecycle states, and repeatable out-of-sample behavior before increasing paper size.

The highest-ROI engineering work is accurate fill-level attribution and a reproducible performance report. Until those exist, account equity is the source of truth and changing strike or exit parameters is premature.

## Paper-trading limitations

Alpaca paper trading is useful for validating integrations and order lifecycle behavior, but it is a simulation. It does not fully model market impact, queue position, latency slippage, or information leakage, and options liquidity can make displayed midpoint results unrealistic. Paper success therefore does not imply live success.

Useful primary references:

- [Alpaca paper trading documentation](https://docs.alpaca.markets/docs/paper-trading)
- [Alpaca credit-spread guide](https://alpaca.markets/learn/credit-spreads)
- [Alpaca options trading guide](https://alpaca.markets/learn/how-to-trade-options-with-alpaca)

## Project map

| Path | Responsibility |
|---|---|
| `agents/` | Structured proposer, advisory critic, prompts, and LLM adapters. |
| `strategy/` | Universe discovery, chain slicing, pricing, structures, and regime features. |
| `risk/` | Deterministic approval and kill-switch rules. |
| `execution/` | Account guard, submit, reconcile, cancel, close, flatten, and recovery. |
| `scheduler/` | Full-cycle orchestration and market-hours loop. |
| `storage/` | SQLite schema, ledger, equity, research, and cycle history. |
| `dashboard/` | Streamlit monitoring, research, STOP, and activity views. |
| `scripts/` | Setup checks, one-shot runs, replay demo, and hosted service startup. |
| `tests/` | Offline unit and integration coverage. |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system design and [AGENTS.md](AGENTS.md) for repository working rules.

## Hosting

Railway uses `railway.toml` to start the scheduler and dashboard together through `scripts/start_service.py`. Streamlit Community Cloud hosts only the dashboard, so the scheduler must run in a separate persistent service. Configure secrets in the host environment, persist the `logs/` volume if you rely on its SQLite ledger, and verify that a service restart runs recovery before new submissions.

## Troubleshooting

- **No trades:** inspect the scheduler JSON results. `stand_down` and risk vetoes are normal; `data_fail`, `bind_fail`, or `missing_account_equity` need investigation.
- **Empty discovered universe:** verify Alpaca data credentials and that candidate assets are active, tradable, optionable, and above the price filter. Discovery fails closed.
- **Order blocked:** confirm paper mode, `EXPECTED_ACCOUNT_ID`, account role, competition gate if used, and options approval level.
- **`NEEDS_REVIEW`:** do not retry manually. Reconcile the client order ID against Alpaca first; ambiguity intentionally blocks duplicate submission.
- **Dashboard runs but nothing trades:** the dashboard is not the scheduler. Run `scheduler.cycle_loop --live` in a persistent process.
- **STOP did not flatten:** the scheduler must be alive and a valid submit path must be available. Review the returned flatten result and broker orders.

ThetaGate is experimental software, not investment advice. Keep it on paper trading while developing and validating it.
