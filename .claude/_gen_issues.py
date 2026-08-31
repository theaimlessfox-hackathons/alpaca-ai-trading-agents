#!/usr/bin/env python3
"""Regenerate epic → issue → subissue tree."""
from pathlib import Path

TS = "2026-08-30T19:53:06Z"
ROOT = Path("/mnt/c/Users/sai95/Desktop/Projects/Alpacca/.claude/epics")

# epic -> [(issue_slug, issue_title, agent, [(name, parallel, depends, conflicts, hours, size, desc, ac, files)])]
TREE = {
    "project-foundation": [
        ("01-repo-bootstrap", "Repo bootstrap", "Senior Developer", [
            ("Write CLAUDE.md", True, [], [], 0.4, "XS",
             "Session source of truth: locked spec, safety invariant, deadline, two accounts.",
             ["CLAUDE.md exists", "LLM never gets place_option_order", "Deadline Fri 4 Sep 2026 21:00 BST / 20:00 UTC", "Two-account pattern documented"],
             ["CLAUDE.md"]),
            ("Create package tree and inits", True, [], [], 0.3, "XS",
             "Empty packages matching plan.md.",
             ["config mcp_integration cli_integration tools agents strategy risk execution scheduler storage dashboard scripts tests docs logs exist", "Each Python package has __init__.py"],
             ["*/__init__.py"]),
            ("Add gitignore and logs keep", True, [], [], 0.2, "XS",
             "Ignore secrets and runtime files.",
             [".gitignore excludes .env .venv logs/*.db logs/*.jsonl __pycache__", "logs/.gitkeep exists"],
             [".gitignore", "logs/.gitkeep"]),
            ("Pin requirements.txt", True, [], [], 0.3, "XS",
             "Runtime deps only.",
             ["Lists mcp alpaca-py streamlit pydantic pydantic-settings apscheduler python-dotenv pandas pytest httpx openai anthropic"],
             ["requirements.txt"]),
        ]),
        ("02-config", "Config and secrets", "Senior Developer", [
            ("Add .env.example two-account slots", False, ["004"], [], 0.3, "XS",
             "Sandbox vs competition key slots. Names only.",
             ["ALPACA_API_KEY ALPACA_SECRET_KEY ALPACA_PAPER_TRADE=true ALPACA_ACCOUNT_ROLE", "Optional ALPACA_COMPETITION_* FEATHERLESS_* ANTHROPIC_API_KEY", "No real keys"],
             [".env.example"]),
            ("Implement settings.py locked knobs", False, ["002", "005"], [], 0.8, "S",
             "pydantic-settings with every locked constant.",
             ["universe SPY QQQ IWM", "DTE 7-21 deltas 0.20-0.30 / 0.10-0.15", "2% 3% 8% max 3 structures", "paper_trade default True", "get_settings() cached"],
             ["config/settings.py"]),
            ("Smoke-import settings", False, ["006"], [], 0.2, "XS",
             "Prove settings load without .env.",
             ["python -c import works with defaults or env"],
             ["config/settings.py"]),
            ("Stub setup_check env validation", False, ["006"], [], 0.4, "XS",
             "Env-only checker. No network.",
             ["Fails if paper flag not true", "Fails if Alpaca or Featherless key missing", "Prints account role"],
             ["scripts/setup_check.py"]),
        ]),
    ],
    "alpaca-stack": [
        ("01-mcp-process", "MCP process", "MCP Builder", [
            ("MCP server supervisor", True, [], [], 1.2, "S",
             "Spawn official alpaca-mcp-server over stdio. Restart on crash.",
             ["Starts with paper env", "kill() is clean", "No live trading"],
             ["mcp_integration/server_manager.py"]),
            ("Async MCP client core", False, ["001"], [], 1.0, "S",
             "connect, list_tools, call_tool.",
             ["Returns raw tool results", "No order helper wrappers"],
             ["mcp_integration/client.py"]),
            ("Client timeouts and close", False, ["002"], [], 0.5, "XS",
             "Hung-tool timeout and clean shutdown.",
             ["Timeouts do not leak processes", "close() idempotent"],
             ["mcp_integration/client.py"]),
        ]),
        ("02-schema-dump", "Schema dump", "MCP Builder", [
            ("Write schema_introspect.py", False, ["002"], [], 0.6, "S",
             "Dump place_option_order, chain, snapshot, account, clock.",
             ["tools/schema_introspect.py writes docs/mcp-schemas/*.json"],
             ["tools/schema_introspect.py"]),
            ("Commit schema JSON dumps", False, ["004"], [], 0.4, "XS",
             "Run against sandbox if keys exist.",
             ["place_option_order.json present or blocker noted", "No secrets in dumps"],
             ["docs/mcp-schemas/"]),
        ]),
        ("03-readonly-tools", "Read-only tools", "MCP Builder", [
            ("Research tool wrappers", False, ["002"], [], 0.8, "S",
             "chain, snapshot, bars, news, clock. No place_*.",
             ["tools/research_tools.py importable", "No order imports"],
             ["tools/research_tools.py"]),
            ("Account tool wrappers", False, ["002"], [], 0.6, "XS",
             "account, positions, portfolio history. Read-only.",
             ["No close/cancel/place helpers"],
             ["tools/account_tools.py"]),
        ]),
        ("04-cli-check", "CLI and setup check", "MCP Builder", [
            ("CLI account command", False, ["002"], [], 0.5, "S",
             "Thin alpaca CLI wrapper for account.",
             ["cli_integration/ops.py account()"],
             ["cli_integration/ops.py"]),
            ("CLI positions command", False, ["008"], [], 0.4, "XS",
             "Thin CLI wrapper for positions.",
             ["ops.positions() parsed"],
             ["cli_integration/ops.py"]),
            ("setup_check live pings", False, ["002", "007", "008"], [], 0.7, "S",
             "Append MCP/CLI/clock/Featherless pings to setup_check.",
             ["Prints options level if available", "Fails if paper false", "Does not place orders"],
             ["scripts/setup_check.py"]),
            ("Print both account IDs", False, ["010"], [], 0.3, "XS",
             "Submission needs the competition account ID.",
             ["Prints sandbox and competition IDs when keys present"],
             ["scripts/setup_check.py"]),
        ]),
    ],
    "risk-gates": [
        ("01-regime", "Regime gate", "Backend Architect", [
            ("Regime types", True, [], [], 0.3, "XS",
             "Trade | StandDown(reason) types.",
             ["strategy/regime.py or types export both"],
             ["strategy/regime.py"]),
            ("Implement regime.py", False, ["001"], [], 0.8, "S",
             "IV-rank / IV-vs-RV / breakout. Deterministic.",
             ["No LLM", "Thresholds from settings or locked defaults"],
             ["strategy/regime.py"]),
            ("test_regime cases", False, ["002"], [], 0.5, "XS",
             "rich / cheap / breakout / missing IV.",
             ["pytest tests/test_regime.py green offline"],
             ["tests/test_regime.py"]),
        ]),
        ("02-universe", "Universe lock", "Backend Architect", [
            ("signals.py SPY QQQ IWM", True, [], [], 0.3, "XS",
             "Yield only locked universe.",
             ["Never yields NVDA"],
             ["strategy/signals.py"]),
            ("test universe lock", False, ["004"], [], 0.3, "XS",
             "Injected extra symbol rejected.",
             ["pytest covers lock"],
             ["tests/test_regime.py or tests/test_signals.py"]),
        ]),
        ("03-engine", "Risk engine", "Backend Architect", [
            ("Verdict types Approve Veto", True, [], [], 0.3, "XS",
             "Approve | Veto(reason).",
             ["risk/engine.py or risk/types.py"],
             ["risk/engine.py"]),
            ("Size DTE delta universe rules", False, ["006"], [], 0.8, "S",
             "Reject bad universe, DTE, deltas, >2% loss, >3 structures, >2 per name.",
             ["Does not trust est_max_loss"],
             ["risk/engine.py"]),
            ("Halt overlap earnings liquidity rules", False, ["006"], [], 0.8, "S",
             "Reject overlap, wide bid-ask, insane IV, earnings-in-life, daily halt, total halt, cooldown, kill switch.",
             ["Each reason distinct"],
             ["risk/engine.py"]),
            ("Recompute max loss", False, ["007"], [], 0.4, "XS",
             "Engine computes max loss from legs and prices.",
             ["Proposer 0.01% claim still vetoed if real risk >2%"],
             ["risk/engine.py"]),
            ("test_risk_engine one case per reason", False, ["007", "008", "009"], [], 1.0, "S",
             "Offline unit tests for every veto plus one approve fixture.",
             ["pytest tests/test_risk_engine.py green", "No network"],
             ["tests/test_risk_engine.py"]),
        ]),
        ("04-kill-switch", "Kill switch and cooldown", "Backend Architect", [
            ("Master flag file", True, [], [], 0.4, "XS",
             "logs/KILL or db flag. read/write.",
             ["on => blocked"],
             ["risk/kill_switch.py"]),
            ("Daily and total halt helpers", False, ["011"], [], 0.5, "S",
             "-3% SOD and -8% start.",
             ["is_halted(equity, sod, start)"],
             ["risk/kill_switch.py"]),
            ("Per-underlying cooldown", False, ["011"], [], 0.4, "XS",
             "60-90 min from settings.",
             ["cooldown_active(symbol, last_ts)"],
             ["risk/kill_switch.py"]),
        ]),
        ("05-structures", "Credit spread mapper", "Backend Architect", [
            ("structures.py + tests", True, [], [], 1.5, "M",
             "TradeProposal -> 2-leg credit spread payload. Condor unused.",
             ["pytest tests/test_structures.py green", "Two legs credit intent"],
             ["strategy/structures.py", "tests/test_structures.py"]),
        ]),
    ],
    "agent-cycle": [
        ("01-contract", "Proposal contract", "AI Engineer", [
            ("TradeProposal model", True, [], [], 0.5, "S",
             "structure expiry legs limit size thesis confidence est_max_loss.",
             ["No order-tool fields"],
             ["agents/schemas.py"]),
            ("CriticNote model", True, [], [], 0.3, "XS",
             "rebuttal + invalidation list.",
             ["agents/schemas.py"],
             ["agents/schemas.py"]),
            ("parse_and_retry fail closed", False, ["001"], [], 0.7, "S",
             "Max 3 tries then None.",
             ["garbage JSON -> None", "valid JSON -> TradeProposal", "tests/test_schemas.py"],
             ["agents/schemas.py", "tests/test_schemas.py"]),
        ]),
        ("02-prompts", "Prompts", "AI Engineer", [
            ("Proposer system prompt", True, [], [], 0.4, "XS",
             "Credit spreads in-band. Locked universe.",
             ["No place_option_order language"],
             ["agents/prompts.py"]),
            ("Critic system prompt", True, [], [], 0.3, "XS",
             "One paragraph + what would change my mind.",
             ["Advisory only"],
             ["agents/prompts.py"]),
        ]),
        ("03-llm", "Featherless client", "AI Engineer", [
            ("Featherless chat client", True, [], [], 1.0, "S",
             "OpenAI-compatible FEATHERLESS_* . Default model.",
             ["Imports without keys", "Anthropic only if USE_ANTHROPIC_FALLBACK=true"],
             ["agents/llm.py"]),
            ("llm smoke()", False, ["006"], [], 0.4, "XS",
             "1-token reply or clear error.",
             ["No throw on missing key"],
             ["agents/llm.py"]),
        ]),
        ("04-agents", "Proposer critic cycle", "AI Engineer", [
            ("run_proposer", False, ["001", "003", "004", "006"], [], 1.2, "S",
             "Prefetched context in. TradeProposal or None out. No tools required.",
             ["Never imports execution"],
             ["agents/proposer.py"]),
            ("run_critic", False, ["002", "005", "006"], [], 0.6, "XS",
             "One short call. Advisory.",
             ["Always returns CriticNote or template fallback"],
             ["agents/critic.py"]),
            ("cycle.py no orders", False, ["008", "009"], [], 1.0, "S",
             "regime -> proposer -> critic. Zero execution imports.",
             ["Stand-down skips LLM"],
             ["agents/cycle.py"]),
            ("test stand-down skips LLM", False, ["010"], [], 0.4, "XS",
             "Mock regime stand-down, assert llm not called.",
             ["offline test"],
             ["tests/test_cycle.py"]),
        ]),
    ],
    "execution-loop": [
        ("01-ledger", "Ledger", "Backend Architect", [
            ("SQLite schema", True, [], [], 0.7, "S",
             "cycles decisions orders equity_history positions_snapshot.",
             ["storage/db.py create"],
             ["storage/db.py"]),
            ("Insert and query helpers", False, ["001"], [], 0.6, "S",
             "Dashboard can read without writes.",
             ["insert+fetch fake cycle"],
             ["storage/db.py"]),
            ("JSONL logger", True, [], [], 0.4, "XS",
             "logs/decisions.jsonl no secrets.",
             ["one line per cycle"],
             ["storage/logger.py"]),
        ]),
        ("02-orders", "Order path", "Backend Architect", [
            ("Executor dry-run", False, ["001"], [], 0.8, "S",
             "Validates risk+kill switch. Places nothing.",
             ["--live required for real order", "No LLM imports"],
             ["execution/executor.py"]),
            ("Executor MCP live", False, ["004"], [], 1.0, "S",
             "Only caller of place_option_order.",
             ["Re-validates immediately before submit"],
             ["execution/executor.py"]),
            ("alpaca-py MLEG fallback", False, ["004"], [], 1.0, "S",
             "OrderClass.MLEG + OptionLegRequest.",
             ["Behind FALLBACK_MLEG", "unit test constructs request"],
             ["execution/alpaca_py_fallback.py"]),
            ("Idempotent client_order_id", False, ["004"], [], 0.4, "XS",
             "Hash of proposal. Retry cannot double-submit.",
             ["same proposal -> same id"],
             ["execution/executor.py"]),
        ]),
        ("03-run", "Scheduler and run_once", "Backend Architect", [
            ("market_hours.py", True, [], [], 0.6, "XS",
             "get_clock + weekend closed test.",
             ["Saturday closed in tests"],
             ["scheduler/market_hours.py"]),
            ("Scheduler name cycle", False, ["004", "008"], [], 1.0, "M",
             "20-30 min per SPY/QQQ/IWM when open. Sleep when closed.",
             ["--once works", "halted => no trade"],
             ["scheduler/loop.py"]),
            ("Snapshot and halt loop", False, ["009"], [], 0.6, "S",
             "5 min equity/positions + daily/total halt check.",
             ["Does not die on halt"],
             ["scheduler/loop.py"]),
            ("Expiry sweep", False, ["009"], [], 0.5, "S",
             "EOD close if <=2 trading days left.",
             ["No rolling logic"],
             ["scheduler/loop.py or risk/kill_switch.py"]),
            ("run_once.py", False, ["004", "009"], [], 0.7, "S",
             "python scripts/run_once.py --symbol SPY default dry-run.",
             ["Prints full transcript"],
             ["scripts/run_once.py"]),
        ]),
    ],
    "operator-desk": [
        ("01-shell", "Desk shell", "Frontend Developer", [
            ("App and PAPER banner", True, [], [], 0.6, "S",
             "streamlit run dashboard/app.py loads.",
             ["Persistent PAPER TRADING banner"],
             ["dashboard/app.py"]),
            ("Header metrics tiles", False, ["001"], [], 0.5, "S",
             "Equity daily P&L open count halt state.",
             ["Fixture numbers if DB empty"],
             ["dashboard/components.py"]),
            ("STOP toggle", False, ["001"], [], 0.5, "S",
             "Writes the same flag kill_switch reads.",
             ["Does not block autonomous loop"],
             ["dashboard/app.py"]),
        ]),
        ("02-book", "Book views", "Frontend Developer", [
            ("Equity curve", False, ["001"], [], 0.6, "S",
             "From equity_history. Simulated label.",
             ["Empty-state copy"],
             ["dashboard/components.py"]),
            ("Positions table", False, ["001"], [], 0.5, "XS",
             "Open structures.",
             ["Renders empty"],
             ["dashboard/components.py"]),
            ("Trade history table", False, ["001"], [], 0.5, "XS",
             "Fills + vetoes with cycle id.",
             ["Includes reason"],
             ["dashboard/components.py"]),
        ]),
        ("03-story", "Decision story", "Frontend Developer", [
            ("Transcript proposal pane", False, ["001"], [], 0.7, "S",
             "Event evidence proposal.",
             ["Rejected cycles first-class"],
             ["dashboard/components.py"]),
            ("Challenge and verdict pane", False, ["007"], [], 0.7, "S",
             "CriticNote + Veto/Approve + optional demo Approve that is inert live.",
             ["Invalidation list visible"],
             ["dashboard/components.py"]),
            ("Activity feed", False, ["001"], [], 0.4, "XS",
             "Halts vetoes fills.",
             ["Recent first"],
             ["dashboard/app.py"]),
            ("Run cycle now button", False, ["009"], [], 0.5, "S",
             "Triggers one cycle. Not a live gate.",
             ["Appears in feed"],
             ["dashboard/app.py"]),
            ("Replay toggle", False, ["007", "008"], [], 0.8, "S",
             "Load fixture. No keys required.",
             ["Works offline"],
             ["dashboard/app.py", "fixtures/replay_spy.json"]),
        ]),
        ("04-host", "Host and runbook", "Frontend Developer", [
            ("README runbook", False, ["001"], [], 0.4, "XS",
             "How to run. Paper only. Env vars.",
             ["No keys in repo"],
             ["README.md"]),
            ("Host Streamlit URL", False, ["012"], [], 0.6, "S",
             "Cloud or Railway.",
             ["Cold visitor can open URL or deploy script exists"],
             ["README.md"]),
        ]),
    ],
    "demo-submission": [
        ("01-form", "Submission form", "Technical Writer", [
            ("List lablab form fields", True, [], [], 0.5, "XS",
             "Video format one-pager slides account ID social slots.",
             ["docs/SUBMISSION_FIELDS.md", "Notes MP4 vs YouTube"],
             ["docs/SUBMISSION_FIELDS.md"]),
            ("Friday SUBMIT checklist", False, ["001"], [], 0.4, "XS",
             "Repo URL MP4 slides write-up account ID 5 socials no keys.",
             ["Target 15:00 BST Friday"],
             ["docs/SUBMIT.md"]),
        ]),
        ("02-docs", "Write-up pack", "Technical Writer", [
            ("ARCHITECTURE.md", True, [], [], 0.8, "S",
             "MCP CLI API proposer critic engine executor. Safety invariant.",
             ["docs/ARCHITECTURE.md"],
             ["docs/ARCHITECTURE.md"]),
            ("One-page WRITEUP.md", True, [], [], 1.2, "S",
             "AI logic, risk gates, Alpaca infra.",
             ["Fits one page", "Names Featherless"],
             ["docs/WRITEUP.md"]),
            ("SLIDES.md 8-10 pages", False, ["004"], [], 1.0, "S",
             "Problem loop memo risk P&L stack next.",
             ["docs/SLIDES.md"],
             ["docs/SLIDES.md"]),
        ]),
        ("03-demo", "Replay and video", "Technical Writer", [
            ("VIDEO.md timed script", True, [], [], 0.8, "S",
             "90s core inside 5 min. Reject critic fill MCP CLI Alpaca UI.",
             ["docs/VIDEO.md"],
             ["docs/VIDEO.md"]),
            ("Note replay_demo.py contract", True, [], [], 0.3, "XS",
             "Spec only unless execution-loop landed. Fixture path.",
             ["docs/VIDEO.md mentions --replay fallback"],
             ["docs/VIDEO.md"]),
        ]),
        ("04-social", "Social prize track", "Technical Writer", [
            ("Post 1 architecture copy", True, [], [], 0.4, "XS",
             "Ready to publish today. Tags @lablabai @AlpacaHQ.",
             ["docs/SOCIAL.md Post 1"],
             ["docs/SOCIAL.md"]),
            ("Posts 2-5 skeletons", False, ["008"], [], 0.4, "XS",
             "Rejected memo, setback, demo clip, results.",
             ["Show critic not rocket P&L"],
             ["docs/SOCIAL.md"]),
        ]),
    ],
}


def fm_task(name, depends, parallel, conflicts, parent):
    dep = "[" + ", ".join(f'"{d}"' for d in depends) + "]"
    conf = "[" + ", ".join(f'"{c}"' for c in conflicts) + "]"
    return f"""---
name: {name}
type: subissue
parent: {parent}
status: open
created: {TS}
updated: {TS}
github: (will be set on sync)
depends_on: {dep}
parallel: {str(parallel).lower()}
conflicts_with: {conf}
---
"""


def body_task(title, desc, ac, files, size, hours, parent, n):
    ac_md = "\n".join(f"- [ ] {x}" for x in ac)
    files_md = "\n".join(f"- `{f}`" for f in files)
    return f"""# Subissue {n}: {title}

## Description

{desc}

## Acceptance Criteria

{ac_md}

## Files

{files_md}

## Effort Estimate

- Size: {size}
- Hours: {hours}

## Definition of Done

- [ ] Acceptance criteria checked
- [ ] Did not edit files owned by another issue
"""


def fm_issue(name, epic, subs, agent):
    sub = "[" + ", ".join(f'"{s}"' for s in subs) + "]"
    return f"""---
name: {name}
type: issue
epic: {epic}
status: open
created: {TS}
updated: {TS}
github: (will be set on sync)
agent: {agent}
subissues: {sub}
progress: 0%
---
"""


stats = {"epics": 0, "issues": 0, "subissues": 0}

global_lines = [
    "---",
    "name: thetagate-issues",
    f"updated: {TS}",
    "---",
    "",
    "# ThetaGate — epics, issues, subissues",
    "",
    "Leaf files stay numbered `001.md` so CCPM can track them. Parents are `issue-XX.md`.",
    "",
]

for epic, issues in TREE.items():
    stats["epics"] += 1
    edir = ROOT / epic
    # wipe old numbered tasks
    for old in edir.glob("[0-9]*.md"):
        old.unlink()
    for old in edir.glob("issue-*.md"):
        old.unlink()

    n = 0
    issue_index = []
    epic_issue_lines = [f"# Issues — {epic}", ""]
    global_lines.append(f"## Epic: `{epic}`")
    global_lines.append("")

    for slug, title, agent, subs in issues:
        stats["issues"] += 1
        parent = f"issue-{slug.split('-', 1)[0]}"
        # slug is 01-repo-bootstrap -> issue-01-repo-bootstrap
        parent_file = f"issue-{slug}"
        sub_nums = []
        sub_rows = []
        for item in subs:
            n += 1
            stats["subissues"] += 1
            name, parallel, depends, conflicts, hours, size, desc, ac, files = item
            num = f"{n:03d}"
            sub_nums.append(num)
            text = fm_task(name, depends, parallel, conflicts, parent_file)
            text += body_task(name, desc, ac, files, size, hours, parent_file, num)
            (edir / f"{num}.md").write_text(text)
            flag = "parallel" if parallel else "seq"
            sub_rows.append(f"  - [ ] `{num}` {name} ({flag}, {size}, {hours}h)")

        issue_body = fm_issue(title, epic, sub_nums, agent)
        issue_body += f"# Issue: {title}\n\n"
        issue_body += f"**Epic:** `{epic}`  \n**Agent:** {agent}  \n**Subissues:** {', '.join(sub_nums)}\n\n"
        issue_body += "## Subissues\n\n" + "\n".join(sub_rows) + "\n\n"
        issue_body += "## Done when\n\n- [ ] Every subissue above is closed\n"
        (edir / f"{parent_file}.md").write_text(issue_body)

        epic_issue_lines.append(f"## {parent_file} — {title}")
        epic_issue_lines.append(f"Agent: **{agent}**")
        epic_issue_lines.append("")
        epic_issue_lines.extend(sub_rows)
        epic_issue_lines.append("")

        global_lines.append(f"### {title} (`{parent_file}`)")
        global_lines.append(f"Agent: **{agent}**")
        global_lines.append("")
        global_lines.extend(sub_rows)
        global_lines.append("")

    (edir / "issues.md").write_text("\n".join(epic_issue_lines) + "\n")

    # patch epic.md tasks section
    epic_path = edir / "epic.md"
    text = epic_path.read_text()
    marker = "## Tasks Created"
    summary = ["## Tasks Created", ""]
    summary.append("See `issues.md` for issue → subissue map.")
    summary.append("")
    summary.append(f"Parent issues: {len(issues)}")
    # count subs
    total_subs = sum(len(s[3]) for s in issues)
    summary.append(f"Subissues: {total_subs}")
    summary.append("")
    for slug, title, agent, subs in issues:
        summary.append(f"- [ ] `issue-{slug}` {title} — {agent} ({len(subs)} subissues)")
    summary.append("")
    if marker in text:
        text = text.split(marker)[0].rstrip() + "\n\n" + "\n".join(summary) + "\n"
    else:
        text = text.rstrip() + "\n\n" + "\n".join(summary) + "\n"
    epic_path.write_text(text)

board = Path("/mnt/c/Users/sai95/Desktop/Projects/Alpacca/.claude/ISSUES.md")
global_lines.append("---")
global_lines.append("")
global_lines.append(f"**Totals:** {stats['epics']} epics · {stats['issues']} issues · {stats['subissues']} subissues")
global_lines.append("")
global_lines.append("Sync later: one GitHub issue per `issue-*.md`, subissues as tasklist or child issues.")
board.write_text("\n".join(global_lines) + "\n")
print(stats)