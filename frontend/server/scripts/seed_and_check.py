"""실행 가능 확인용 시드 스크립트 (STEP 5~6 검증).

  python -m app.scripts.seed_and_check

DB 생성 → 전역 규칙/데모 사용자/mock 거래 시드 → 간단 요약 출력.
숫자 계산이 아니라 '데이터가 제대로 적재됐는지' 눈으로 확인하는 용도.
"""
from __future__ import annotations

from collections import defaultdict

from server.config import settings
from server.core import clock
from server.core import categories as C
from server.db.database import init_db, session_scope
from server.db.models import Transaction
from server.providers.mock_provider import MockFinancialDataProvider


def run() -> None:
    print(f"▶ DEMO_TODAY = {clock.today()}  |  DB = {settings.database_url}")
    init_db()

    provider = MockFinancialDataProvider()
    with session_scope() as s:
        rules = provider.ensure_global_rules(s)
        user = provider.ensure_demo_user(s)
        added = provider.sync_transactions(s, user.id)
        print(f"▶ 전역 가맹점 규칙 +{rules}  |  사용자='{user.name}'(id={user.id})  |  거래 +{added}")

    with session_scope() as s:
        txs = s.query(Transaction).filter(Transaction.user_id == user.id).all()
        income = [t for t in txs if t.tx_type == C.INCOME]
        expense = [t for t in txs if t.tx_type == C.EXPENSE]

        by_cat: dict[str, float] = defaultdict(float)
        for t in expense:
            by_cat[t.category] += t.amount

        first = min(t.tx_date for t in txs)
        last = max(t.tx_date for t in txs)

        print("\n=== MoneyMate 시드 요약 ===")
        print(f"기간            : {first} ~ {last}")
        print(f"총 거래         : {len(txs)}건 (지출 {len(expense)} / 소득 {len(income)})")
        print(f"총 지출         : {sum(t.amount for t in expense):,.0f}원")
        print(f"총 소득         : {sum(t.amount for t in income):,.0f}원")

        print("\n[카테고리별 지출]")
        for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
            print(f"  {cat:<8} {amt:>12,.0f}원")

        credit = sum(t.amount for t in expense if t.payment_method == C.CREDIT)
        print(f"\n신용카드 지출 합 : {credit:,.0f}원 (다음 결제 예정액 계산 대상)")

        print("\n[최근 7일 거래]")
        recent = sorted(
            [t for t in txs if (last - t.tx_date).days <= 6],
            key=lambda t: t.tx_date,
        )
        for t in recent:
            sign = "＋" if t.tx_type == C.INCOME else "－"
            memo = f"  ({t.memo})" if t.memo else ""
            print(f"  {t.tx_date}  {sign}{t.amount:>8,.0f}  {t.category:<7} {t.merchant}{memo}")

    print("\n✅ STEP 5~6 완료: 스키마 생성 + Mock 데이터 적재 OK")


if __name__ == "__main__":
    run()
