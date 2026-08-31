# Official submission fields — Alpaca AI Trading Agents Hackathon

Last check: **2026-08-30**.

| Source | Opened? | Notes |
|---|---|---|
| Event page https://lablab.ai/ai-hackathons/alpaca-ai-trading-agents-hackathon | Yes (full-page scrape 2026-08-29; live dashboard 2026-08-30) | Primary for challenge rules |
| Live dashboard `.../live` | Yes | Submissions open; track **Options Alpha Agents** |
| Generic lablab deliverable guide https://lablab.ai/delivering-your-hackathon-solution | Yes | Shared across events |
| Authenticated **Submit project** wizard | **No** | Cloudflare blocks anonymous curl; no team login in this workspace |

Anything that exists only on the wizard stays *form-unverified*.

## Deadline

| Claim | Verdict |
|---|---|
| Dates **28 August – 4 September 2026** | **Public-page verified** (event + live + listing) |
| Schedule line: **End of Submissions! 4 Sep 9:00 PM Bangladesh Standard Time** | **Public-page verified** (event schedule block). That is **UTC+6 → 20:00 UTC / 4:00 PM ET** |
| Hero banner “Submission deadline Sep 4, 9:00 PM BST” | Same page; **BST = Bangladesh Standard Time**, not British Summer Time |
| Prize hero **$6,000** vs body **$6,300** | Both appear on public pages. Body itemizes $2,500 + $300 Featherless / $1,500 / $1,000 / 2×$500 |
| Wizard clock | *form-unverified* |

**Ship rule:** submit with a multi-hour buffer before **4 Sep 20:00 UTC**. Do not wait for the NYSE close.

## Eligibility (public event page)

Verified on the event page scrape:

1. Autonomous AI trading agent on Alpaca **Trading API**.
2. Must use Alpaca **MCP server or CLI**.
3. **Every strategy must incorporate options.**
4. Paper trading only for the competition.
5. **Brand-new paper account** dedicated to this hackathon. Reused accounts are not eligible.
6. Starting balance **$100,000**.
7. Disclose **Alpaca paper trading account ID** (judges use it for P&L).
8. One-page write-up: AI logic, risk gates, Alpaca infra.

Track on live dashboard: **Options Alpha Agents**.

## Submit wizard fields (compose from event page + generic guide)

### Always expect (generic lablab + this event)

| Field | Rule | Source |
|---|---|---|
| Project title | required | generic + event |
| Short description | ≤255 chars (generic) | generic |
| Long description | ≥100 words (generic) | generic |
| Track | Options Alpha Agents | live dashboard |
| Technology & category tags | include Alpaca, options, MCP | event |
| Cover image | PNG or JPG, 16:9 recommended | generic |
| Video | Generic: **MP4 file upload**, **≤5 minutes**, not a YouTube link; some guides say ≤300 MB | generic; *this event’s widget *form-unverified* |
| Slide presentation | **PDF** | generic + event |
| Public GitHub | required | event + generic |
| Demo platform + Application URL | required; Streamlit/Replit/Vercel cited in generic rules | generic + event |
| Alpaca paper account ID | **required for judging** | **event-specific** |
| Social links | up to **5** X/LinkedIn; tag lablab + Alpaca | event |

### One-pager

Event: “One-page write-up covering AI logic, risk gates, and Alpaca infrastructure.”  
Whether that is a **file upload** or the long description is *form-unverified*. Write `docs/WRITEUP.md` either way.

### Not on this event (ignore unless the wizard shows them)

IBM Bob report (appears in some other lablab guides).

## Judging (event page)

- P&L on the dedicated paper account
- Technology implementation (API, MCP, CLI)
- Creativity & originality
- Presentation & execution
- Social is a separate prize (quality + engagement)

## Recheck on the logged-in form before Thursday

- [ ] Video widget: file vs URL
- [ ] Deadline timestamp printed on the form
- [ ] Account ID + any $100k screenshot field
- [ ] One-pager upload vs textarea
- [ ] Extra partner fields

## What we treat as locked for build

Public page is enough to lock: **options**, **MCP or CLI**, **new $100k paper account**, **account ID on submit**, **one-pager**, **buffer before 4 Sep 20:00 UTC**. Video: prepare an **MP4 ≤5 min** per generic lablab; swap if the form disagrees.
