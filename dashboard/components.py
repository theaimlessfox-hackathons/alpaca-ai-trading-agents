from __future__ import annotations

import json

import streamlit as st


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
    if points:
        st.line_chart(points)
    else:
        st.info("No equity history yet.")


def positions(rows: list[dict]) -> None:
    st.subheader("Positions")
    if rows:
        st.table(rows)
    else:
        st.info("No open structures.")


def history(rows: list[dict]) -> None:
    st.subheader("Trade history")
    if rows:
        st.table(rows)
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
