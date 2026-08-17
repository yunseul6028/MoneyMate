"""애플리케이션 설정. .env 에서 로드하며, 없으면 안전한 기본값을 사용한다.

원칙: LLM 키가 없어도 전체 파이프라인이 돌아가야 한다 → LLM_PROVIDER 기본값은 'mock'.
"""
from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 어느 디렉토리에서 실행하든 backend/.env 를 찾도록 절대경로 사용.
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"

# Vercel(서버리스)은 cwd 가 읽기전용 → SQLite 는 쓰기 가능한 /tmp 에.
_DEFAULT_DB = (
    "sqlite:////tmp/moneymate.db"
    if os.environ.get("VERCEL")
    else "sqlite:///./moneymate.db"
)


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
    database_url: str = _DEFAULT_DB

    # --- 앱의 '오늘' (날짜 감각의 단일 소스) ---
    # live_date=False: demo_today 로 고정(데모·재현성). True: 실제 date.today() 사용.
    # 앱 전역은 settings 를 직접 보지 말고 app.core.clock 의 today()/now() 를 쓴다.
    demo_today: date = date(2026, 8, 15)
    live_date: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
