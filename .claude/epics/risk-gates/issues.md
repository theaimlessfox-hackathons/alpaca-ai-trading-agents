# Issues — risk-gates

## issue-01-regime — Regime gate
Agent: **Backend Architect**

  - [ ] `001` Regime types (parallel, XS, 0.3h)
  - [ ] `002` Implement regime.py (seq, S, 0.8h)
  - [ ] `003` test_regime cases (seq, XS, 0.5h)

## issue-02-universe — Universe lock
Agent: **Backend Architect**

  - [ ] `004` signals.py SPY QQQ IWM (parallel, XS, 0.3h)
  - [ ] `005` test universe lock (seq, XS, 0.3h)

## issue-03-engine — Risk engine
Agent: **Backend Architect**

  - [ ] `006` Verdict types Approve Veto (parallel, XS, 0.3h)
  - [ ] `007` Size DTE delta universe rules (seq, S, 0.8h)
  - [ ] `008` Halt overlap earnings liquidity rules (seq, S, 0.8h)
  - [ ] `009` Recompute max loss (seq, XS, 0.4h)
  - [ ] `010` test_risk_engine one case per reason (seq, S, 1.0h)

## issue-04-kill-switch — Kill switch and cooldown
Agent: **Backend Architect**

  - [ ] `011` Master flag file (parallel, XS, 0.4h)
  - [ ] `012` Daily and total halt helpers (seq, S, 0.5h)
  - [ ] `013` Per-underlying cooldown (seq, XS, 0.4h)

## issue-05-structures — Credit spread mapper
Agent: **Backend Architect**

  - [ ] `014` structures.py + tests (parallel, M, 1.5h)

