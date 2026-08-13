"""설정에 따라 LLM Provider 를 만든다.

키가 없으면 자동으로 mock 으로 폴백 → 앱이 항상 실행 가능(원칙 준수).
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.llm.base import LLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.openai_compatible import OpenAICompatibleProvider


def build_llm() -> LLMProvider:
    p = (settings.llm_provider or "mock").lower()

    if p == "gemini" and settings.gemini_api_key:
        return OpenAICompatibleProvider(
            base_url=settings.gemini_base_url,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            name="gemini",
        )
    if p == "openai" and settings.openai_api_key:
        return OpenAICompatibleProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            name="openai",
        )
    if p in ("openai_compatible", "compat") and settings.compat_api_key:
        return OpenAICompatibleProvider(
            base_url=settings.compat_base_url,
            api_key=settings.compat_api_key,
            model=settings.compat_model,
            name="openai_compatible",
        )

    return MockLLMProvider()


@lru_cache
def get_llm() -> LLMProvider:
    return build_llm()
