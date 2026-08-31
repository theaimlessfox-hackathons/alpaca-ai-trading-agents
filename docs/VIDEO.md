# Video (≤5 min MP4)

Backup if live data dies: `PYTHONPATH=. python scripts/replay_demo.py --fixture fixtures/replay_spy.json`

0:00–0:25 Hook — sells defined-risk premium when IV/RV is rich; Python can veto the model.

0:25–3:00 Desk — reject (show veto) → different proposal → fill/monitor. MCP chat: account/positions/orders/market data (e.g. "what's my buying power?"), not ThetaGate's own logic. CLI: `alpaca account`. Alpaca paper UI.

3:00–4:15 P&L, max loss, why gates exist.

4:15–5:00 Stack recap. Do not claim Alpaca MCP can halt ThetaGate.
