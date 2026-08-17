"""MockFinancialDataProvider — mock 원장을 DB 에 적재하는 프로바이더.

실제 카드/은행 API 대신, app.data.mock_data 로 생성한 현실적 원장을 원천으로 쓴다.
나중에 RealFinancialDataProvider 가 같은 인터페이스로 오픈뱅킹 데이터를 넣으면 된다.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from server.core import clock
from server.data.merchant_rules import GLOBAL_MERCHANT_RULES
from server.db.models import MerchantRule, Transaction, User, UserProfile
from server.providers.base import FinancialDataProvider


def _load_ledger(today: date) -> dict:
    """데모 원장 로드.

    app/data/demo_ledger.py(실 은행 내역 기반, git 미포함)가 있으면 그것을,
    없으면(예: 클론 직후) 합성 mock 데이터를 사용한다. → 데이터 없이도 앱이 돈다.
    """
    try:
        from server.data.demo_ledger import load_demo_ledger

        return load_demo_ledger()
    except ImportError:
        from server.data.mock_data import generate_mock_ledger

        return generate_mock_ledger(today)


class MockFinancialDataProvider(FinancialDataProvider):
    def __init__(self, today: date | None = None):
        self.today = today or clock.today()

    def ensure_global_rules(self, session: Session) -> int:
        """전역 가맹점 규칙을 (없으면) 적재."""
        existing = {
            r.merchant_key
            for r in session.query(MerchantRule).filter(MerchantRule.user_id.is_(None))
        }
        added = 0
        for key, category in GLOBAL_MERCHANT_RULES.items():
            if key not in existing:
                session.add(MerchantRule(merchant_key=key, category=category,
                                         user_id=None, source="rule"))
                added += 1
        session.flush()
        return added

    def ensure_demo_user(self, session: Session) -> User:
        """데모 사용자 + 프로필을 (없으면) 생성해 반환."""
        user = session.query(User).order_by(User.id.asc()).first()
        if user:
            return user
        ledger = _load_ledger(self.today)
        p = ledger["profile"]
        user = User(name=p["name"])
        session.add(user)
        session.flush()
        session.add(UserProfile(
            user_id=user.id,
            monthly_budget=p["monthly_budget"],
            card_billing_day=p["card_billing_day"],
        ))
        session.flush()
        return user

    def sync_transactions(self, session: Session, user_id: int) -> int:
        """mock 원장을 DB 에 적재. 이미 거래가 있으면 skip(멱등)."""
        already = (
            session.query(Transaction)
            .filter(Transaction.user_id == user_id)
            .count()
        )
        if already:
            return 0
        ledger = _load_ledger(self.today)
        added = 0
        for t in ledger["transactions"]:
            session.add(Transaction(
                user_id=user_id,
                tx_date=t.tx_date,
                merchant=t.merchant,
                amount=t.amount,
                category=t.category,
                tx_type=t.tx_type,
                payment_method=t.payment_method,
                direction=getattr(t, "direction", "out"),
                category_source="seed",
                memo=t.memo,
            ))
            added += 1
        session.flush()
        return added
