# ThetaGate architecture

```
Alpaca data (MCP + CLI)
        → regime (ATM IV / 20d RV)          # Python
        → proposer (Featherless, Claude live failover)  # no order tools
        → critic (advisory, wired into the live cycle)
        → risk engine + kill switch         # Python
        → executor / broker                 # only place_option_order path
        → SQLite + JSONL
        → Streamlit desk
```

**Safety:** the LLM never receives `place_option_order`. Close is one atomic multi-leg order or fail closed. Halt flattens via `flatten_all`, then blocks new orders.

Official Alpaca MCP chat: account / positions / orders / market only. It cannot halt us or read SQLite.
