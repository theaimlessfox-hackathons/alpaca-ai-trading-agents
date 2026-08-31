# Alpaca AI Trading Agents Hackathon Plan

## Product concept: Alpaca Sentinel

Alpaca Sentinel is an explainable portfolio-risk agent. It continuously monitors an Alpaca paper portfolio, detects unusual risk or market events, proposes a response, and executes only after deterministic safety checks and explicit user approval.

Example:

> NVDA fell sharply after negative news. Sentinel found that semiconductor exposure is now 41%, modeled three responses, rejected one for breaching the daily-loss rule, and recommends reducing NVDA by 20%. Approve?

After approval, Sentinel submits the paper order, tracks execution, and records why the decision was made.

The differentiator is not another generic trading chatbot. It is an end-to-end, auditable agent that demonstrates genuine agency while keeping trading controlled and explainable.

## MVP workflow

```text
Portfolio + prices + news
          |
          v
     Event detector
          |
          v
  Analyst generates thesis
          |
          v
 Deterministic risk engine
          |
          v
    Proposed trade plan
          |
          v
 Human approval or rejection
          |
          v
 Alpaca paper order + audit log
```

### Core features

- Portfolio dashboard showing equity, buying power, positions, exposure, and recent P&L.
- Event detector for large price moves, concentration, drawdown, and relevant news.
- AI-generated explanations that include evidence, confidence, and uncertainty.
- Deterministic risk rules:
  - Maximum position size
  - Maximum sector exposure
  - Maximum order value
  - Daily-loss limit
  - Duplicate-order prevention
  - Stale-data rejection
- Trade preview with Approve and Reject controls.
- Alpaca paper-order execution and status tracking.
- Decision timeline showing evidence, proposal, risk checks, approval, and fill.

## Technical approach

- Frontend: Next.js, TypeScript, Tailwind CSS, and shadcn/ui.
- Backend: FastAPI or Next.js server routes; choose whichever gets to a working demo fastest.
- Trading integration: Alpaca MCP for agent operations, with `alpaca-py` or direct API calls where tighter control is useful.
- AI: A reliable tool-calling model with schema-constrained responses.
- Data: SQLite locally; use Supabase only if deployment requires it.
- Charts: Recharts.
- Deployment: Vercel plus Railway/Render, or one Next.js deployment.

Use the LLM only for interpreting evidence, forming a thesis, challenging a proposal, and explaining decisions. Position sizing, limits, validation, idempotency, and execution permissions must remain deterministic application code.

All development and demonstrations must use Alpaca paper trading. Never commit API keys. Include a `.env.example` containing placeholder variable names only.

## Build schedule

The event ends September 4, 2026. The project should be feature-complete by September 2, leaving September 3 for submission work and September 4 as a buffer.

### August 30: foundation and dashboard

- Create and verify an Alpaca paper account.
- Confirm account, positions, quotes, news, and paper-order access.
- Scaffold the application.
- Define the exact 90-second demo story.
- Add `.env.example` and secret-safe configuration.
- Build the portfolio overview and position table.
- Implement exposure, concentration, and drawdown calculations.

Success criterion: the application reads a real Alpaca paper account, presents it cleanly, and a test script can place and cancel a tiny paper order.

### August 31: agent workflow

- Implement price, news, concentration, and drawdown event detection.
- Make the model return structured output containing:
  - Observation
  - Evidence
  - Thesis
  - Confidence
  - Proposed action
  - Invalidation conditions
- Validate every response against a schema.
- Store each run in the audit timeline.

Success criterion: one action produces a grounded, readable proposal tied to portfolio and market evidence.

### September 1: risk controls and execution

- Implement deterministic risk policies.
- Add trade preview, approval, rejection, and order-status flows.
- Add idempotency protection so repeated actions cannot submit duplicate orders.
- Display a persistent PAPER TRADING indicator.
- Handle rejected, partially filled, canceled, and failed orders.

Success criterion: an approved proposal becomes a tracked Alpaca paper order, while unsafe proposals are visibly blocked.

### September 2: differentiator and polish

- Add a critic step called **Challenge this trade** that argues against the analyst's recommendation.
- Display **What would change my mind?** using explicit invalidation conditions.
- Polish the decision timeline, evidence presentation, loading states, and error handling.
- Add a replay mode with saved demo data for use when markets or external APIs are unavailable.

Success criterion: the full demo works live and in deterministic replay mode.

### September 3: submission package

- Deploy a stable build.
- Write the README with setup, architecture, safety model, limitations, and screenshots.
- Record a backup demo video.
- Create a simple architecture graphic.
- Prepare concise submission copy.
- Test from a clean browser and fresh environment.
- Rehearse the presentation repeatedly.

### September 4: buffer and submission

- Fix critical problems only.
- Do not add infrastructure or major features.
- Submit early and verify that every submitted link works.

## Demo script

1. Open with: **Most AI traders focus on finding trades. Sentinel focuses on preventing poorly controlled ones.**
2. Show the real Alpaca paper portfolio.
3. Trigger or select a detected price/news event.
4. Show the analyst's thesis, confidence, evidence, and invalidation conditions.
5. Run **Challenge this trade** and show the counterargument.
6. Show an aggressive trade being rejected by the deterministic risk engine.
7. Show the safer alternative and its passed risk checks.
8. Approve it.
9. Display the Alpaca order status and complete audit trail.
10. Finish with: **The model proposes; deterministic policy controls; the user authorizes.**

Keep the primary demo under 90 seconds. Maintain a recorded backup and a seeded replay scenario.

## Metrics to display

- Risks detected
- Proposals blocked by policy
- User approval and rejection counts
- Portfolio concentration before and after a proposal
- Agent response latency
- Order success and failure status
- Percentage of claims linked to market data or news evidence

Do not imply that paper-trading performance equals live performance. Clearly state that simulation may not capture actual market impact, information leakage, latency slippage, or queue position.

## Explicit non-goals

Do not build these before the complete MVP works:

- Live-money trading
- Multiple broker integrations
- Custom model training
- Social features
- Complex backtesting infrastructure
- Options strategies
- Voice control
- Fully autonomous continuous execution
- A large multi-agent system

One analyst, one critic, and one deterministic risk engine are sufficient.

## Product principle

The pitch is not **our AI predicts prices**. The pitch is:

> Alpaca Sentinel turns noisy market information into an auditable, policy-controlled action and proves the complete workflow through Alpaca.
