from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


# Discord embed limits — see https://discord.com/developers/docs/resources/channel#embed-limits
EMBED_TITLE_MAX = 256
EMBED_DESC_MAX = 4096
EMBEDS_PER_MESSAGE = 10


@dataclass
class SummarizedArticle:
    title: str
    url: str
    summary: str
    source: str
    authors: list[str]
    published: str | None


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


EMBED_COLOR = 0x5865F2


def build_topic_message(topic: str, items: list[SummarizedArticle]) -> dict[str, Any]:
    """One Discord message: a short content header + one embed per article.

    Discord renders per-article embeds as stacked cards with a clickable bold
    title, an authors line, the summary, and a source/date footer.
    """
    n = len(items)
    content = f"## 📰 {topic} — {n} pick{'s' if n != 1 else ''}"

    embeds: list[dict[str, Any]] = []
    for it in items:
        parts: list[str] = []
        if it.authors:
            shown = ", ".join(it.authors[:3]) + ("…" if len(it.authors) > 3 else "")
            parts.append(f"*{shown}*")
        parts.append(it.summary)
        description = "\n\n".join(parts)

        footer_bits = [b for b in (it.source, it.published) if b]
        embed: dict[str, Any] = {
            "title": _truncate(it.title, EMBED_TITLE_MAX),
            "url": it.url,
            "description": _truncate(description, EMBED_DESC_MAX),
            "color": EMBED_COLOR,
        }
        if footer_bits:
            embed["footer"] = {"text": " • ".join(footer_bits)}
        embeds.append(embed)

    return {"content": content, "embeds": embeds}


def post(webhook_url: str, *, content: str | None = None, embeds: list[dict[str, Any]] | None = None) -> None:
    payload: dict[str, Any] = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds[:EMBEDS_PER_MESSAGE]
    r = requests.post(webhook_url, json=payload, timeout=30)
    r.raise_for_status()
