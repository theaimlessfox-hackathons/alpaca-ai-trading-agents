"""Research page: today's scan, articles the desk used, older tickets."""

from __future__ import annotations

import streamlit as st

from dashboard.components import article_board, banner, blotter_board, scan_board
from storage.db import create_all, latest_scan, list_articles, list_trade_blotter, trading_session_date

banner()
st.title("Research")
st.caption("Selected names for this US session, headlines the desk read, and the paper blotter.")

create_all()
today = trading_session_date()
scan = latest_scan(today)
fallback: list[str] = []
if scan is None:
    try:
        from strategy.signals import iter_universe

        fallback = list(iter_universe())
    except Exception:  # noqa: BLE001 - page must still render
        fallback = []

scan_board(scan, fallback)
article_board(list_articles(today))
blotter_board(list_trade_blotter(limit=50))
