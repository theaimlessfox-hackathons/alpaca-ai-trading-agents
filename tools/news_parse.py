"""Normalize Alpaca news payloads into headline rows for the desk."""

from __future__ import annotations

from typing import Any


def news_items(raw: Any, *, limit: int = 5) -> list[dict[str, str]]:
    items = raw.get("news", raw) if isinstance(raw, dict) else raw
    if isinstance(items, dict):
        items = items.get("news") or items.get("articles") or []
    out: list[dict[str, str]] = []
    for article in items or []:
        if not isinstance(article, dict):
            continue
        headline = article.get("headline") or article.get("title") or article.get("summary")
        if not headline:
            continue
        url = article.get("url") or article.get("source_url") or ""
        source = article.get("source") or article.get("author") or ""
        out.append({"headline": str(headline), "url": str(url), "source": str(source)})
        if len(out) >= limit:
            break
    return out
