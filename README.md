# ThetaGate

Paper-only options credit-spread desk for the Alpaca AI Trading Agents Hackathon.

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # paper keys only
PYTHONPATH=. pytest -q
PYTHONPATH=. python scripts/run_once.py --symbol SPY
PYTHONPATH=. python scripts/replay_demo.py
PYTHONPATH=. streamlit run dashboard/app.py
```

**Host:** [Streamlit Community Cloud](https://share.streamlit.io) — repo + `dashboard/app.py`. Or Railway (`railway.toml`). Secrets stay in the host env, never in git.

Never set `ALPACA_PAPER_TRADE=false`. See `CLAUDE.md` and `docs/SUBMISSION_FIELDS.md`.
