from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


SEEN_RETENTION_DAYS = 60


class SeenStore:
    """Tracks article IDs we've already summarized, per topic.

    Layout on disk:
        { "<topic>": { "<article_id>": "YYYY-MM-DD", ... }, ... }
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.data: dict[str, dict[str, str]] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = {}

    def is_seen(self, topic: str, article_id: str) -> bool:
        return article_id in self.data.get(topic, {})

    def mark_seen(self, topic: str, article_id: str, today: date) -> None:
        self.data.setdefault(topic, {})[article_id] = today.isoformat()

    def prune(self, today: date, retention_days: int = SEEN_RETENTION_DAYS) -> None:
        cutoff = today - timedelta(days=retention_days)
        for topic, entries in list(self.data.items()):
            kept = {
                aid: d
                for aid, d in entries.items()
                if d >= cutoff.isoformat()
            }
            if kept:
                self.data[topic] = kept
            else:
                del self.data[topic]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
