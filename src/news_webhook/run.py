from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from .config import Config, TopicConfig, PubMedSource, RSSSource, load_config
from .discord import SummarizedArticle, build_topic_message, post
from .llm.base import LLMProvider, get_provider
from .scheduler import is_due
from .sources.base import Article
from .sources.enrich import enrich
from .sources.pubmed import fetch_pubmed
from .sources.rss import fetch_rss
from .state import SeenStore


log = logging.getLogger("news_webhook")


def pick_with_llm(
    candidates: list[Article],
    *,
    criteria: str,
    limit: int,
    llm: LLMProvider,
) -> list[Article]:
    """Ask the LLM to pick up to `limit` candidates that match `criteria`.

    Returns [] if nothing qualifies, so the topic stays silent on quiet days.
    """
    if not candidates:
        return []

    lines = []
    for i, a in enumerate(candidates[:40]):  # cap context size
        snippet = (a.summary or "").replace("\n", " ").strip()[:400]
        src = a.source or ""
        lines.append(f"[{i}] {a.title}\n    source: {src}\n    {snippet}")

    prompt = (
        "You are curating a Discord digest. Pick up to "
        f"{limit} of the most interesting candidates that match this criteria:\n\n"
        f"{criteria.strip()}\n\n"
        "Be selective: it is fine to return FEWER than the limit, or NONE if "
        "nothing strongly matches. Do not stretch to fill the quota.\n\n"
        f"Candidates:\n{chr(10).join(lines)}\n\n"
        "Reply with just the indices of your picks, one per line, in order of "
        "interest. No prose, no explanation, no other text. If nothing qualifies, "
        "reply with the single word NONE."
    )

    try:
        reply = llm.complete(prompt)
    except Exception as e:
        log.warning("relevance gate failed (%s) — falling back to first N", e)
        return candidates[:limit]

    if "NONE" in reply.upper().split():
        return []

    picked_idx: list[int] = []
    for line in reply.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        if token.isdigit():
            idx = int(token)
            if 0 <= idx < len(candidates) and idx not in picked_idx:
                picked_idx.append(idx)
                if len(picked_idx) >= limit:
                    break
    return [candidates[i] for i in picked_idx]


def collect_articles(topic: TopicConfig) -> list[Article]:
    all_items: list[Article] = []
    for src in topic.sources:
        try:
            if isinstance(src, PubMedSource):
                all_items.extend(fetch_pubmed(src.query, topic.max_articles, src.sort))
            elif isinstance(src, RSSSource):
                all_items.extend(fetch_rss(src.url, topic.max_articles))
        except Exception as e:
            log.warning("source failed (%s): %s", getattr(src, "type", "?"), e)

    # Stable dedup by id, preserving order.
    seen_ids: set[str] = set()
    deduped: list[Article] = []
    for a in all_items:
        if a.id and a.id not in seen_ids:
            seen_ids.add(a.id)
            deduped.append(a)
    return deduped


def run_topic(
    topic: TopicConfig,
    cfg: Config,
    seen: SeenStore,
    today: date,
    *,
    dry_run: bool,
) -> dict | None:
    log.info("→ topic '%s'", topic.name)
    candidates = collect_articles(topic)
    log.info("  %d candidates fetched", len(candidates))

    fresh = [a for a in candidates if not seen.is_seen(topic.name, a.id)]
    log.info("  %d fresh after dedup", len(fresh))
    if not fresh:
        log.info("  nothing new — skipping")
        return None

    llm = get_provider(
        cfg.llm.provider,
        model=cfg.llm.model,
        api_key=os.environ[cfg.llm.api_key_env],
        params=cfg.llm.params,
    )

    if topic.relevance_check:
        picks = pick_with_llm(
            fresh,
            criteria=topic.relevance_criteria or "interesting and relevant to the topic",
            limit=topic.max_articles,
            llm=llm,
        )
        log.info("  %d picked by LLM relevance gate", len(picks))
        if not picks:
            log.info("  nothing relevant — skipping")
            return None
    else:
        picks = fresh[: topic.max_articles]

    if topic.enrich_fulltext:
        picks = [enrich(a) for a in picks]

    style = topic.style or cfg.default_style

    summarized: list[SummarizedArticle] = []
    for art in picks:
        text = art.best_text
        if not text.strip():
            log.warning("  skipping %s — no text", art.url)
            continue
        try:
            s = llm.summarize(text, style=style)
        except Exception as e:
            log.warning("  llm failed on %s: %s — falling back to abstract", art.url, e)
            s = (art.summary or "")[:500]
        summarized.append(SummarizedArticle(
            title=art.title or "(untitled)",
            url=art.url,
            summary=s,
            source=art.source,
            authors=art.authors,
            published=art.published,
        ))

    if not summarized:
        return None

    payload = build_topic_message(topic.name, summarized)

    if dry_run:
        print(json.dumps(payload, indent=2))
    else:
        webhook = os.environ[cfg.discord.webhook_url_env]
        post(webhook, content=payload["content"], embeds=payload["embeds"])
        for art in picks:
            seen.mark_seen(topic.name, art.id, today)

    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="news-webhook")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--state", default="state/seen.json")
    p.add_argument("--topic", action="append", help="run only this topic (repeatable)")
    p.add_argument("--dry-run", action="store_true", help="print payload, don't post or save state")
    p.add_argument("--today", help="override today's date (YYYY-MM-DD) for testing frequency")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    # Load .env for local runs; no-op in CI where vars come from secrets.
    load_dotenv()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    today = datetime.fromisoformat(args.today).date() if args.today else date.today()
    cfg = load_config(args.config)
    seen = SeenStore(args.state)

    filter_names = set(args.topic) if args.topic else None
    any_posted = False

    for topic in cfg.topics:
        if not topic.enabled:
            continue
        if filter_names and topic.name not in filter_names:
            continue
        if not filter_names and not is_due(topic.frequency, today):
            log.info("skip '%s' — not due today (%s)", topic.name, topic.frequency)
            continue
        try:
            result = run_topic(topic, cfg, seen, today, dry_run=args.dry_run)
            any_posted = any_posted or result is not None
        except Exception as e:
            log.exception("topic '%s' failed: %s", topic.name, e)

    if not args.dry_run and any_posted:
        seen.prune(today)
        seen.save()

    return 0 if any_posted or args.dry_run else 0  # never fail the cron on "nothing to post"


if __name__ == "__main__":
    sys.exit(main())
