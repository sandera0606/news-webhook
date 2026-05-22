from __future__ import annotations

from .base import build_prompt


class GroqProvider:
    def __init__(self, *, model: str, api_key: str, temperature: float = 0.3) -> None:
        from groq import Groq

        self.model = model
        self.temperature = temperature
        self._client = Groq(api_key=api_key)

    def summarize(self, article_text: str, *, style: str) -> str:
        return self.complete(build_prompt(article_text, style))

    def complete(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()
