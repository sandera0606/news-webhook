from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Article:
    id: str                      # stable dedup key (DOI, PMID, URL, GUID)
    title: str
    url: str
    summary: str = ""            # abstract or excerpt as fetched
    full_text: str | None = None # populated by enrich step if available
    source: str = ""             # human-readable origin ("PubMed", "arXiv cs.AI")
    authors: list[str] = field(default_factory=list)
    published: str | None = None # ISO date if known
    doi: str | None = None
    pmid: str | None = None

    @property
    def best_text(self) -> str:
        return self.full_text or self.summary or self.title
