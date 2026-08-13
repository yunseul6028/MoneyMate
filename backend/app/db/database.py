"""DB 엔진/세션. MVP는 SQLite, 스키마는 Postgres 호환.

DATABASE_URL 만 바꾸면 Supabase/Postgres 로 그대로 이전 가능하다.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


# SQLite 전용 옵션(check_same_thread)은 sqlite 일 때만 적용.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """모든 테이블 생성 (없을 때만)."""
    # models 를 import 해야 Base.metadata 에 테이블이 등록된다.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """트랜잭션 경계를 관리하는 세션 컨텍스트."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI 의존성 주입용 세션 제너레이터."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
