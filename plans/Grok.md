# Alpaca AI Trading Agents Hackathon

Plan of action for [lablab.ai × Alpaca](https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon).

- **Window:** 28 Aug – 4 Sep 2026 (online)
- **Deadline:** Friday 4 Sep, 9:00 PM BST
- **Today:** Sunday 30 Aug 2026 — 5 days left, 5 US cash sessions (Mon–Fri)
- **Prize pool:** $6,300 (1st $2,500 + $300 Featherless, 2nd $1,500, 3rd $1,000, 2× $500 social)
- **Workspace:** this repo (`Alpacca`)

---

## Hard requirements (do not miss)

- Autonomous agent on Alpaca’s Trading API
- **MCP or CLI** (use both)
- **Options in every strategy**
- **Brand-new paper account**, starting balance **$100,000**
- One-page write-up: AI logic, risk gates, Alpaca infra
- Public GitHub, hosted demo, video ≤5 min (MP4 upload, not a YouTube link), slides, paper account ID
- Paper accounts already get **Level 3 multi-leg** — no extra options application

Judges score **P&L**, **Alpaca stack usage**, **originality**, and **presentation**. Social is a separate prize.

---

## What to build

**A regime-gated premium desk, not a directional sniper.**

Working name: **ThetaGate** (alt: Aegis Desk).

The agent sells **defined-risk options premium** (put/call credit spreads, iron condors on liquid ETFs: SPY, QQQ, IWM, maybe 1–2 mega-caps) when implied vol is rich, and it **stands down or hedges** when the regime is breakout / cheap-vol.

| Typical team | This project |
|---|---|
| YOLO long calls / “options sniper” | Theta works every session |
| Unlimited loss shorts | Hard max loss per trade |
| One fat LLM prompt | LLM proposes, Python vetoes |
| Dashboard of P&L only | Decision memos + kill-switch log |
| API-only | API + MCP operator chat + CLI cron |

Current public submissions cluster around hedging, long-gamma, and generic multi-agent desks. Defined-risk income with a visible critic is still open, and it is the strategy most likely to finish the week green.

Do **not** train a custom model this week. Features and gates, not a 5-day training loop.

---

## Locked spec (do not change)

- **Universe:** SPY / QQQ / IWM
- **Structures:** put credit spread first; iron condor only if Monday works
- **DTE:** 7–21
- **Delta:** short ~0.20–0.30, long ~0.10–0.15
- **Risk:** ≤2% of $100k per structure, 3 open structures max, −3% daily halt, −8% total halt

P&L target for the week is **not** +20%. Target **small positive or flat with bounded drawdown and a full audit trail**.

---

## Architecture

```
Alpaca market data (bars, option chain, Greeks, news)
        │
        ▼
 Feature + regime layer          ← deterministic Python
 (IV rank, RV vs IV, VIX, earnings calendar, liquidity)
        │
        ▼
 Strategy agent                  ← Featherless LLM ($25 credits)
 "propose a 1–2 credit spread / condor with strikes, size, thesis"
        │
        ▼
 Critic / risk guard             ← NO LLM
 max 2% account risk, 1 underlying, no earnings inside 3 days,
 buying-power check, no overlapping shorts, daily loss halt
        │
        ▼
 Executor                        ← alpaca-py + `alpaca` CLI
 multi-leg orders, then a 5–15 min monitor
        │
        ▼
 Operator surface
 Streamlit desk  +  MCP chat ("why did we sell the SPY put spread?")
```

**Risk gates stay in Python.** The LLM never places an order.

Use Featherless for the proposal agent (partner-prize path). Use Alpaca MCP as the operator interface and the CLI for the always-on loop.

### Repo layout

```
agent/          regime, proposal, critic
broker/         alpaca-py wrapper + CLI wrappers
monitor/        position + P&L loop
app/            Streamlit desk
logs/           decision memos (jsonl)
```

---

## Clock

US cash is closed until **Monday 9:30 ET**. The competition account must exist **before Monday open**.

### Done / overdue — Sat 29 Aug

- [ ] Enroll on lablab, join [Discord](https://discord.gg/lablabai), create a team (1–6; solo is fine)
- [ ] Two Alpaca paper accounts: **sandbox** (break things) + **competition** (fresh, $100k, submission ID)
- [ ] Confirm both are paper, Level 3 options; place a 1-lot credit spread by hand
- [ ] Claim Featherless credits ([setup PDF](https://storage.googleapis.com/lablab-static-eu/share/Hackathon-Setup-Guide-ALPACA26.pdf))
- [ ] Post #1 on X and LinkedIn: problem + architecture. Tag `@lablabai` `@AlpacaHQ`

### Today — Sun 30 Aug (scaffold until a fake trade works)

Sunday exit criteria — all of these, no extras:

- [ ] `get_account` on the **sandbox** key
- [ ] Pull SPY chain + Greeks
- [ ] Critic rejects a bad proposal (earnings, size, overlapping)
- [ ] Critic accepts a good one and places a **sandbox** multi-leg order
- [ ] MCP answers “what’s my buying power?” and “show open positions”
- [ ] CLI can run `account` / `positions` / `place-spread`
- [ ] Streamlit shows account, positions, last 5 memos

If this is not green by Sunday night, cut the condor and the second agent. Keep the put-spread + critic.

### Mon 31 Aug (first real paper on the judged account)

Before 9:30 ET, switch the running agent to the **fresh $100k account**. Do not trade the sandbox ID for judging.

- Morning: 1–2 small defined-risk puts on SPY/QQQ
- Intraday: monitor loop, flatten if a gate fires
- After close: screenshot P&L, export memos
- Post #2: first live decision memo, including a **rejected** trade

### Tue–Wed 1–2 Sep (make it look like a product)

- Tighten strikes/size from Monday fills (paper options fill weird; log mid vs fill)
- Add iron condor **only** if Monday’s spreads behaved
- Desk UI: equity curve, open risk, gate hits, “why this trade” cards
- MCP: `explain last trade`, `halt trading`, `show risk budget`
- One replay script: “given this snapshot, here is the proposal + critic verdict” (demo money shot)
- Post #3: a setback (bad fill, veto, flattened position) and what you changed

### Thu 3 Sep (submission assets, not features)

Freeze the strategy at lunch. No new structures.

| Asset | Spec |
|---|---|
| Demo | Streamlit on Streamlit Cloud / Railway / Vercel, keys in env, **paper only** |
| GitHub | public, README with architecture + how to run + paper-only warning |
| One-pager | AI logic, risk gates, MCP/CLI/API map. Required. |
| Slides | 8–10 pages: problem, agent loop, one real memo, risk table, P&L, stack, next step |
| Video | **≤5 min MP4**, uploaded file, not a YouTube link |
| Social | posts 4–5 (recap + demo clip) |

#### Video (≤5 min)

1. **0:00–0:25** — “Most hackathon options bots pick a direction. This one sells defined risk when IV is rich and a Python critic can veto the model.”
2. **0:25–3:00** — live desk: proposal → critic reject → proposal → fill → monitor. Show MCP chat and a CLI command. Show the Alpaca paper account.
3. **3:00–4:15** — P&L, max loss, why the gates exist.
4. **4:15–5:00** — stack (Trading API + MCP + CLI + Featherless) and what you’d add after the week.

### Fri 4 Sep (buffer and submit)

Submit **by ~3:00 PM BST** (6+ hours early). Confirm:

- [ ] Fresh account ID, $100k start
- [ ] Options trades visible on that account
- [ ] Application URL loads without local setup
- [ ] Video plays, slides open, GitHub is public
- [ ] One-pager uploaded / pasted in long description
- [ ] Up to 5 social links, both orgs tagged
- [ ] Tags include Alpaca, options, MCP, Featherless

Do not ship a Friday rewrite.

---

## Social track

Two $500 awards score **post quality and engagement**. Cap is 5 links.

1. Sat — architecture
2. Mon — first memo + a rejection
3. Tue/Wed — a failure and the fix
4. Thu — 30s demo clip
5. Fri — results + repo

Every post tags **@lablabai** and **@AlpacaHQ** (X) / the matching LinkedIn pages. Show the critic, not a rocket-ship P&L screenshot.

---

## What not to build

- Directional 0DTE lottery tickets
- Five research agents before one spread works
- Crypto, unless it is a tiny extra — **options are mandatory**
- Fine-tuning, RAG-over-SEC-filings, or a custom gym
- Live trading keys anywhere
- Reusing an old paper account for the submission ID

---

## Winning vs finishing

**Finish line (eligible):** autonomous loop, options fills on a fresh $100k paper account, MCP or CLI in the path, hosted demo, video, write-up.

**Podium line:** the critic is real (show rejected trades), P&L is bounded and preferably green, the desk is clickable, and the video makes the idea obvious in 25 seconds.

---

## Links

- Hackathon: https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon
- Live dashboard: https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon/live
- Discord: https://discord.gg/lablabai
- Alpaca paper signup: https://alpaca.markets/?utm_source=website&utm_medium=event&utm_campaign=lablab_hackathon
- Getting started: https://docs.alpaca.markets/us/docs/getting-started
- Trading API: https://docs.alpaca.markets/us/docs/getting-started-with-trading-api
- Market data: https://docs.alpaca.markets/us/docs/getting-started-with-alpaca-market-data
- MCP server: https://docs.alpaca.markets/us/docs/alpaca-mcp-server
- CLI: https://docs.alpaca.markets/us/docs/alpacas-cli · https://github.com/alpacahq/cli
- Python SDK: https://github.com/alpacahq/alpaca-py
- Alpaca skills: https://github.com/alpacahq/alpaca-skills
- Multi-agent reference: https://alpaca.markets/learn/building-a-multi-agent-ai-trading-system-on-alpaca
- Featherless setup: https://storage.googleapis.com/lablab-static-eu/share/Hackathon-Setup-Guide-ALPACA26.pdf
- lablab guidelines: https://lablab.ai/ai-articles/hackathon-guidelines
- How to win: https://lablab.ai/guide/how-to-win-an-ai-hackathon
