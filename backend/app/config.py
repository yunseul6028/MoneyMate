"""애플리케이션 설정. .env 에서 로드하며, 없으면 안전한 기본값을 사용한다.

원칙: LLM 키가 없어도 전체 파이프라인이 돌아가야 한다 → LLM_PROVIDER 기본값은 'mock'.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM ---
    llm_provider: str = "mock"  # mock | openai
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # --- DB ---
    database_url: str = "sqlite:///./moneymate.db"

    # --- 데모 기준 '오늘' ---
    # 실서비스에서는 date.today() 를 쓰지만, 데모/재현성을 위해 고정 날짜를 사용.
    demo_today: date = date(2026, 8, 13)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
