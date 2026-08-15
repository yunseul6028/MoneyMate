"""DB 스키마 (STEP 5).

MVP 테이블
  users               데모 사용자 (MVP는 단일 사용자)
  user_profiles       월 생활비/카드 결제일 등 금융 컨텍스트
  transactions        거래내역 (소득/지출) — 서비스의 원천 데이터
  merchant_rules      가맹점→카테고리 매핑 (전역 규칙 + 사용자 개인화 override)
  agent_events        Agent 가 '먼저 말을 건' 기록 (proactive 메시지)
  chat_messages       채팅 히스토리

설계 노트
  - amount 는 항상 양수. 소득/지출 구분은 tx_type 으로.
  - payment_method='credit' 인 지출은 '다음 카드 결제 예정액' 계산에 쓰인다.
  - merchant_rules.user_id 가 NULL 이면 전역 규칙, 값이 있으면 그 사용자 개인화.
  - Postgres 이전을 고려해 JSON 컬럼과 표준 타입만 사용.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    # 기록 시각도 앱의 단일 시계를 따른다(알림 피로 로직이 같은 타임라인 위에서 동작).
    from app.core.clock import now

    return now()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserProfile(Base):
    """월 단위 금융 컨텍스트. 예산 계산·시뮬레이션의 기준값."""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    # 이번 달 쓸 수 있는 생활비 예산 (용돈+알바 등으로 스스로 정한 목표치)
    monthly_budget: Mapped[float] = mapped_column(Float, default=600_000)
    # 신용카드 결제일 (매월 며칠). 다음 결제 예정액 계산에 사용.
    card_billing_day: Mapped[int] = mapped_column(Integer, default=14)

    user: Mapped["User"] = relationship(back_populates="profile")


class Transaction(Base):
    """거래 한 건. 서비스의 원천 데이터.

    구조 예시(스펙): id, date, merchant, amount, category, payment_method
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    tx_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    merchant: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)  # 항상 양수
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    tx_type: Mapped[str] = mapped_column(String(10), default="expense")  # expense | income | transfer
    payment_method: Mapped[str] = mapped_column(String(20), default="check")
    # 돈의 방향: out(나감) | in(들어옴). 송금 정산 계산에 사용.
    direction: Mapped[str] = mapped_column(String(4), default="out")

    # 분류 출처: rule | user | llm | seed — 개인화/디버깅용
    category_source: Mapped[str] = mapped_column(String(10), default="rule")
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_tx_user_date", "user_id", "tx_date"),
    )


class MerchantRule(Base):
    """가맹점 → 카테고리 매핑.

    user_id 가 NULL 이면 전역 규칙(CU→식음료 등),
    값이 있으면 그 사용자의 개인화 override(사용자가 분류를 수정한 결과).
    조회 시 개인화 규칙을 전역보다 우선한다.
    """

    __tablename__ = "merchant_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 정규화된 가맹점 키워드 (소문자/공백정리). 예: "스타벅스", "cu"
    merchant_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(10), default="rule")  # rule | user | llm
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("merchant_key", "user_id", name="uq_merchant_user"),
    )


class PersonRule(Base):
    """송금 상대(사람) → 관계·카테고리 기억.

    처음 본 사람은 unresolved. 사용자가 '친구 정산'/'다른 용도'로 답하면 저장.
      kind: friend(정산) | other(중고거래 등)
      category: friend→식음료(기본), other→사용자가 고른 카테고리
    이후 같은 사람 송금은 자동으로 이 카테고리로 처리(정산 netting 포함).
    """

    __tablename__ = "person_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    person_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), default="friend")  # friend | other
    category: Mapped[str] = mapped_column(String(40), default="식음료")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "person_key", name="uq_person_user"),
    )


class AgentEvent(Base):
    """Agent 가 사용자에게 '먼저 말을 건' 기록.

    decision: NO_INTERVENTION | ASK_CONTEXT | WARN | COACH
    analysis: 판단 근거가 된 분석 스냅샷(JSON) — 왜 개입했는지 추적.
    """

    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(60), nullable=False)  # 예: food_delivery_spike
    message: Mapped[str] = mapped_column(Text, nullable=False)  # 코치가 건넨 자연어
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class ChatMessage(Base):
    """채팅 히스토리. role: user | assistant | system."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 이 메시지가 어떤 도구/분석을 참조했는지 (디버깅·투명성)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
