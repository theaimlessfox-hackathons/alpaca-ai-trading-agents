from __future__ import annotations

import json

import streamlit as st

_TABLE_SKIP = {"proposal_json", "critic_json"}


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def table_markdown(rows: list[dict]) -> str:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in _TABLE_SKIP and key not in keys:
                keys.append(key)
    if not keys:
        return ""
    header = "| " + " | ".join(keys) + " |"
    sep = "| " + " | ".join("---" for _ in keys) + " |"
    body = [
        "| " + " | ".join(_cell(row.get(key)) for key in keys) + " |"
        for row in rows
    ]
    return "\n".join([header, sep, *body])


def markdown_table(rows: list[dict]) -> None:
    """Render a markdown table. Avoids st.table/st.dataframe so a broken
    local numpy/pyarrow stack cannot take down the desk."""
    text = table_markdown(rows)
    if not text:
        st.info("No columns to show.")
        return
    st.markdown(text)


def banner() -> None:
    st.markdown("### PAPER TRADING")
    st.caption("Simulated funds. Not live performance.")


def tiles(equity: float, daily_pnl: float, open_n: int, killed: bool) -> None:
    a, b, c, d = st.columns(4)
    a.metric("Equity", f"${equity:,.0f}")
    b.metric("Daily P&L", f"${daily_pnl:,.0f}")
    c.metric("Open structures", open_n)
    d.metric("Halt", "ON" if killed else "off")


def curve(points: list[float]) -> None:
    st.subheader("Equity")
    if not points:
        st.info("No equity history yet.")
        return
    try:
        st.line_chart(points)
    except Exception:  # noqa: BLE001 - numpy/pyarrow breakage must not blank the desk
        st.text(" → ".join(f"{p:,.0f}" for p in points[-12:]))


def positions(rows: list[dict]) -> None:
    st.subheader("Positions")
    if rows:
        markdown_table(rows)
    else:
        st.info("No open structures.")


def history(rows: list[dict]) -> None:
    st.subheader("Trade history")
    if rows:
        markdown_table(rows)
    else:
        st.info("No cycles yet.")


def transcript(rows: list[dict]) -> None:
    """Regression fix: this used to read row["thesis"]/row["critic"], but
    storage.db.recent_cycles() rows only ever have id/verdict/reason/proposal_json
    -- neither key existed, so this panel never showed a parsed thesis. Extracts
    thesis from proposal_json instead; falls back to the raw JSON if parsing
    fails or there's nothing structured to read."""
    st.subheader("Decision transcript")
    if not rows:
        st.info("No memos.")
        return
    for row in rows:
        with st.expander(f"{row.get('verdict')} — {row.get('reason')}"):
            thesis = None
            raw = row.get("proposal_json")
            if raw:
                try:
                    thesis = json.loads(raw).get("thesis")
                except (json.JSONDecodeError, TypeError, AttributeError):
                    thesis = None
            st.write(thesis or raw or "")
            critic_raw = row.get("critic_json") or row.get("critic")
            if critic_raw:
                try:
                    note = json.loads(critic_raw) if isinstance(critic_raw, str) else critic_raw
                    st.caption("Critic: " + note.get("rebuttal", ""))
                except (json.JSONDecodeError, TypeError, AttributeError):
                    st.caption(str(critic_raw))


def activity(lines: list[str]) -> None:
    st.subheader("Activity")
    for line in lines or ["quiet"]:
        st.text(line)


def scan_board(scan: dict | None, fallback: list[str] | None = None) -> None:
    st.subheader("Today's scan")
    symbols = (scan or {}).get("symbols") or list(fallback or [])
    if not symbols:
        st.info("No scan stored for this session yet.")
        return
    if scan and scan.get("ts"):
        st.caption(f"Session {scan.get('session_date')} · selected {scan.get('ts')}")
    markdown_table([{"#": i + 1, "symbol": sym} for i, sym in enumerate(symbols)])


def article_board(rows: list[dict]) -> None:
    st.subheader("Articles used")
    if not rows:
        st.info("No headlines stored for today's scan yet.")
        return
    shown = [
        {
            "symbol": r.get("symbol"),
            "source": r.get("source") or "",
            "headline": r.get("headline"),
            "url": r.get("url") or "",
        }
        for r in rows
    ]
    markdown_table(shown)


def blotter_board(rows: list[dict]) -> None:
    st.subheader("Trade blotter")
    if not rows:
        st.info("No paper tickets yet.")
        return
    markdown_table(rows)
