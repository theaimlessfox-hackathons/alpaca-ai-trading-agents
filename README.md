# ThetaGate

Paper-only options credit-spread desk for the Alpaca AI Trading Agents Hackathon.

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # paper keys only
PYTHONPATH=. pytest -q
PYTHONPATH=. python scripts/run_once.py --symbol SPY
PYTHONPATH=. python scripts/replay_demo.py
PYTHONPATH=. streamlit run dashboard/app.py
PYTHONPATH=. python -m scheduler.cycle_loop --live  # continuous paper trading
```

**Host:** Railway (`railway.toml`) starts both the dashboard and continuous
paper-trading scheduler. Streamlit Community Cloud runs the dashboard only;
run the scheduler separately if you host there. Secrets stay in the host env,
never in git.

Never set `ALPACA_PAPER_TRADE=false`. See `CLAUDE.md` and `docs/SUBMISSION_FIELDS.md`.
