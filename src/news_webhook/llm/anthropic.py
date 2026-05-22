from __future__ import annotations

from .base import build_prompt


class AnthropicProvider:
    def __init__(self, *, model: str, api_key: str, max_tokens: int = 512, temperature: float = 0.3) -> None:
        import anthropic

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = anthropic.Anthropic(api_key=api_key)

    def summarize(self, article_text: str, *, style: str) -> str:
        return self.complete(build_prompt(article_text, style))

    def complete(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts).strip()
