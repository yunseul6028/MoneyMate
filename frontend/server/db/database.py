"""DB 엔진/세션. MVP는 SQLite, 스키마는 Postgres 호환.

DATABASE_URL 만 바꾸면 Supabase/Postgres 로 그대로 이전 가능하다.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from server.config import settings


class Base(DeclarativeBase):
    pass


if settings.database_url.startswith("sqlite"):
    # SQLite 전용 옵션(check_same_thread).
    engine = create_engine(
        settings.database_url, connect_args={"check_same_thread": False}, future=True
    )
else:
    # 관리형 Postgres + 서버리스: 커넥션을 함수 호출 간에 들고 있지 않도록 NullPool,
    # 끊긴 커넥션 자동 감지 pre_ping.
    engine = create_engine(
        settings.database_url, poolclass=NullPool, pool_pre_ping=True, future=True
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """모든 테이블 생성 (없을 때만)."""
    # models 를 import 해야 Base.metadata 에 테이블이 등록된다.
    from server.db import models  # noqa: F401

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
