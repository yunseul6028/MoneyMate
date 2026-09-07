"""애플리케이션 설정. .env 에서 로드하며, 없으면 안전한 기본값을 사용한다.

원칙: LLM 키가 없어도 전체 파이프라인이 돌아가야 한다 → LLM_PROVIDER 기본값은 'mock'.
"""
from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 어느 디렉토리에서 실행하든 backend/.env 를 찾도록 절대경로 사용.
_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _normalize_db_url(url: str) -> str:
    """DATABASE_URL 정규화.

    - 빈값이면 Postgres env(POSTGRES_URL 등) → 없으면 SQLite 기본값.
    - Neon/Vercel/Supabase 는 'postgres://' 로 주지만 SQLAlchemy 2.x 는
      'postgresql+psycopg://' 스킴이 필요 → 변환. psycopg(v3) 드라이버 사용.
    - Postgres 인데 sslmode 없으면 require 추가(관리형 DB 는 SSL 필수).
    """
    url = url or os.environ.get("POSTGRES_URL") or os.environ.get("POSTGRES_PRISMA_URL") or ""
    if not url:
        # Vercel(서버리스)은 cwd 가 읽기전용 → SQLite 는 쓰기 가능한 /tmp 에.
        return "sqlite:////tmp/moneymate.db" if os.environ.get("VERCEL") else "sqlite:///./moneymate.db"
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+psycopg://") and "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


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
    # 빈값이면 validator 가 POSTGRES_URL → SQLite 순으로 결정 + 스킴 정규화.
    database_url: str = ""

    @field_validator("database_url")
    @classmethod
    def _resolve_database_url(cls, v: str) -> str:
        return _normalize_db_url(v)

    # --- 앱의 '오늘' (날짜 감각의 단일 소스) ---
    # live_date=False: demo_today 로 고정(데모·재현성). True: 실제 date.today() 사용.
    # 앱 전역은 settings 를 직접 보지 말고 app.core.clock 의 today()/now() 를 쓴다.
    demo_today: date = date(2026, 8, 15)
    live_date: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
