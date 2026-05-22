from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    def summarize(self, article_text: str, *, style: str) -> str: ...
    def complete(self, prompt: str) -> str: ...


def build_prompt(article_text: str, style: str) -> str:
    return (
        f"{style.strip()}\n\n"
        "Article text follows. Output only the summary — no preamble, "
        "no headers, no bullet lists unless the style asks for them.\n\n"
        "---\n"
        f"{article_text.strip()[:16000]}"
    )


def get_provider(name: str, model: str, api_key: str, params: dict[str, Any] | None = None) -> LLMProvider:
    params = params or {}
    if name == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model=model, api_key=api_key, **params)
    if name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model=model, api_key=api_key, **params)
    if name == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(model=model, api_key=api_key, **params)
    if name == "groq":
        from .groq import GroqProvider
        return GroqProvider(model=model, api_key=api_key, **params)
    raise ValueError(f"unknown LLM provider: {name}")
