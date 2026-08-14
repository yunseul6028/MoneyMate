"""소비 분석 엔진 검증 (STEP 8).  python -m app.scripts.check_analysis"""
from __future__ import annotations

from app.core import clock
from app.db.database import init_db, session_scope
from app.providers.mock_provider import MockFinancialDataProvider
from app.services.analysis import analyze


def _won(n: float) -> str:
    return f"{n:,.0f}원"


def _pct(r: float | None) -> str:
    return "—" if r is None else f"{r*100:+.0f}%"


def run() -> None:
    init_db()
    provider = MockFinancialDataProvider()
    with session_scope() as s:
        provider.ensure_global_rules(s)
        user = provider.ensure_demo_user(s)
        provider.sync_transactions(s, user.id)
        uid = user.id

    with session_scope() as s:
        r = analyze(s, uid, clock.today())

    print(f"=== 소비 분석 ({r.today}) — {user.name} ===\n")
    print("[이번 달]")
    print(f"  총 지출        {_won(r.month_expense)}  (지난달 동기간 {_won(r.last_month_expense)}, {_pct(r.month_change_rate)})")
    print(f"  총 소득        {_won(r.month_income)}")
    print(f"  예산           {_won(r.monthly_budget)}  →  남은 예산 {_won(r.remaining_budget)}")
    print(f"  경과           {r.days_elapsed}/{r.days_in_month}일")
    print(f"  예상 월지출     {_won(r.projected_month_expense)}  →  예산 대비 {_won(r.projected_remaining_budget)}")

    print("\n[주간]")
    print(f"  이번 주(7일)   {_won(r.week_expense)}  (직전 4주 평균 {_won(r.avg_weekly_expense)}, {_pct(r.week_increase_rate)})")
    print(f"  배달           이번주 {_won(r.delivery_week)}  vs 평소 {_won(r.delivery_baseline_week_avg)}")

    print("\n[카드]")
    print(f"  다음 결제 예정  {_won(r.upcoming_card_bill)}  (결제일 {r.next_billing_date})")

    print("\n[카테고리별 이번 달 지출]")
    for c in r.categories:
        print(f"  {c.category:<8} {_won(c.month_amount):>12}  비중 {c.share*100:4.0f}%  "
              f"주간 {_won(c.week_amount)}(평소 {_won(c.baseline_week_avg)}, {_pct(c.increase_rate)})")

    print("\n[급증 카테고리 (주간 +30%↑)]")
    for t in r.top_categories_increase:
        print(f"  ⚠ {t['category']}: {_won(t['week_amount'])} (평소 {_won(t['baseline_week_avg'])}, {_pct(t['increase_rate'])})")

    print("\n[구독 (이번 달)]")
    for sub in r.subscriptions:
        print(f"  {sub['date']}  {sub['merchant']:<14} {_won(sub['amount'])}")
    print(f"  구독 합계: {_won(sum(x['amount'] for x in r.subscriptions))}")

    print("\n[일회성 대형 지출 (이번 달, 5만원↑)]")
    for l in r.large_one_time:
        memo = f" ({l['memo']})" if l.get("memo") else ""
        print(f"  {l['date']}  {l['merchant']:<14} {_won(l['amount'])} [{l['category']}]{memo}")

    print("\n✅ STEP 8 완료: deterministic 소비 분석 OK")


if __name__ == "__main__":
    run()
