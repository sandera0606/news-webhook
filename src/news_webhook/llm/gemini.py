from __future__ import annotations

from .base import build_prompt


class GeminiProvider:
    def __init__(self, *, model: str, api_key: str, temperature: float = 0.3) -> None:
        from google import genai

        self.model = model
        self.temperature = temperature
        self._client = genai.Client(api_key=api_key)

    def summarize(self, article_text: str, *, style: str) -> str:
        return self.complete(build_prompt(article_text, style))

    def complete(self, prompt: str) -> str:
        from google.genai import types

        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=self.temperature),
        )
        return (resp.text or "").strip()
