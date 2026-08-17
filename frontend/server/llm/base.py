"""LLM Provider 추상화 (STEP 10).

원칙(13-3, 13-4): LLM 은 판단·맥락·대화·개인화에만 쓴다. 숫자 계산은 시키지 않는다.
provider 를 갈아끼울 수 있게 인터페이스로 분리(Gemini/OpenAI/호환/mock).
`available` 이 False 면 상위 로직은 규칙기반 fallback 을 쓴다 → 키 없이도 앱이 돌아감.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"
    available: bool = False

    @abstractmethod
    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 600,
    ) -> str:
        """system+user 프롬프트로 1턴 생성. 실패 시 예외를 던진다."""
