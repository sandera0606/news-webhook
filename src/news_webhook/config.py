from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator


Frequency = Literal["daily", "weekly", "weekdays", "weekends"]
SourceType = Literal["pubmed", "rss"]
ProviderName = Literal["gemini", "anthropic", "openai", "groq"]


class DiscordConfig(BaseModel):
    webhook_url_env: str = "DISCORD_WEBHOOK_URL"


class LLMConfig(BaseModel):
    provider: ProviderName
    model: str
    api_key_env: str
    params: dict[str, Any] = Field(default_factory=dict)


class PubMedSource(BaseModel):
    type: Literal["pubmed"]
    query: str
    sort: Literal["relevance", "date"] = "relevance"


class RSSSource(BaseModel):
    type: Literal["rss"]
    url: str


SourceConfig = PubMedSource | RSSSource


class TopicConfig(BaseModel):
    name: str
    enabled: bool = True
    frequency: Frequency = "daily"
    max_articles: int = Field(default=5, ge=1, le=25)
    enrich_fulltext: bool = False
    style: str | None = None
    sources: list[SourceConfig]

    # Relevance gate: if true, an LLM picks up to `max_articles` candidates
    # that match `relevance_criteria`. Returns nothing if none qualify, so
    # the topic stays silent on uninteresting days.
    relevance_check: bool = False
    relevance_criteria: str | None = None

    @field_validator("sources")
    @classmethod
    def _at_least_one_source(cls, v: list[SourceConfig]) -> list[SourceConfig]:
        if not v:
            raise ValueError("topic must declare at least one source")
        return v


class Config(BaseModel):
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    llm: LLMConfig
    default_style: str = (
        "Write a concise 2-3 sentence summary aimed at a technically literate "
        "reader. Lead with the most newsworthy finding. No marketing language."
    )
    topics: list[TopicConfig]


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
