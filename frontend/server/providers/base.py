"""Data Provider Layer — 금융 데이터 원천 추상화.

원칙 10: 실제 금융 API 연결을 대비해 원천을 분리한다.
  - MockFinancialDataProvider  (지금 사용: seed 된 mock 데이터)
  - RealFinancialDataProvider  (나중: 카드사/은행 오픈뱅킹 API)

Provider 는 '원천에서 거래를 가져와 우리 DB 에 적재'하는 책임만 진다.
분석/판단/대화는 상위 레이어의 몫이다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from sqlalchemy.orm import Session

from server.db.models import Transaction


class FinancialDataProvider(ABC):
    """금융 데이터 원천 인터페이스."""

    @abstractmethod
    def sync_transactions(self, session: Session, user_id: int) -> int:
        """원천에서 최신 거래를 가져와 DB 에 적재. 새로 추가된 건수를 반환."""

    def get_transactions(
        self,
        session: Session,
        user_id: int,
        start: date | None = None,
        end: date | None = None,
        tx_type: str | None = None,
    ) -> list[Transaction]:
        """기간/유형으로 거래 조회 (원천 무관 공통 구현)."""
        q = session.query(Transaction).filter(Transaction.user_id == user_id)
        if start is not None:
            q = q.filter(Transaction.tx_date >= start)
        if end is not None:
            q = q.filter(Transaction.tx_date <= end)
        if tx_type is not None:
            q = q.filter(Transaction.tx_type == tx_type)
        return q.order_by(Transaction.tx_date.asc()).all()
