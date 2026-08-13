"""애플리케이션 설정. .env 에서 로드하며, 없으면 안전한 기본값을 사용한다.

원칙: LLM 키가 없어도 전체 파이프라인이 돌아가야 한다 → LLM_PROVIDER 기본값은 'mock'.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 어느 디렉토리에서 실행하든 backend/.env 를 찾도록 절대경로 사용.
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH), env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM ---
    # mock | gemini | openai | openai_compatible
    llm_provider: str = "mock"

    # Gemini (OpenAI 호환 엔드포인트 사용)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # OpenAI 호환 (Groq/Together/OpenRouter/Ollama 등)
    compat_api_key: str = ""
    compat_model: str = ""
    compat_base_url: str = ""

    # --- DB ---
    database_url: str = "sqlite:///./moneymate.db"

    # --- 데모 기준 '오늘' ---
    # 실서비스에서는 date.today() 를 쓰지만, 데모/재현성을 위해 고정 날짜를 사용.
    demo_today: date = date(2026, 8, 13)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
