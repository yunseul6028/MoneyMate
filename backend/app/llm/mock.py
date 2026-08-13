"""Mock LLM — 키가 없을 때 쓰는 폴백. available=False 로 상위에 신호."""
from __future__ import annotations

from app.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    name = "mock"
    available = False

    def chat(self, system: str, user: str, *, temperature: float = 0.7,
             max_tokens: int = 600) -> str:
        # 실제로 호출되면 안 되지만, 방어적으로 빈 문자열 반환.
        return ""
