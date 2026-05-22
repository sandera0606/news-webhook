from __future__ import annotations

from .base import build_prompt


class OpenAIProvider:
    def __init__(self, *, model: str, api_key: str, temperature: float = 0.3, base_url: str | None = None) -> None:
        from openai import OpenAI

        self.model = model
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    def summarize(self, article_text: str, *, style: str) -> str:
        return self.complete(build_prompt(article_text, style))

    def complete(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()
