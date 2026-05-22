from __future__ import annotations

import hashlib
import re
from typing import Any

import feedparser

from .base import Article


_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s or "").strip()


def _entry_id(entry: Any, feed_url: str) -> str:
    for key in ("id", "guid", "link"):
        val = entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)
        if val:
            return f"rss:{val}"
    h = hashlib.sha1(
        (feed_url + (entry.get("title") or "")).encode("utf-8")
    ).hexdigest()
    return f"rss:{h}"


def fetch_rss(url: str, max_articles: int) -> list[Article]:
    parsed = feedparser.parse(url)
    source_name = parsed.feed.get("title", url) if hasattr(parsed, "feed") else url
    out: list[Article] = []
    for entry in parsed.entries[: max_articles * 3]:
        title = _strip_html(entry.get("title", ""))
        link = entry.get("link", "")
        summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
        published = entry.get("published") or entry.get("updated") or None
        authors = []
        if entry.get("author"):
            authors = [entry["author"]]
        out.append(
            Article(
                id=_entry_id(entry, url),
                title=title,
                url=link,
                summary=summary,
                source=source_name,
                authors=authors,
                published=published,
            )
        )
    return out
