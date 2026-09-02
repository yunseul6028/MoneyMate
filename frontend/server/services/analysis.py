"""소비 분석 엔진 (STEP 8).

원칙(13-2, 13-4): 금융 관련 숫자는 전부 여기서 deterministic 코드로 계산한다.
LLM 은 이 결과를 '해석·설명'만 한다. 절대 숫자를 LLM 에게 계산시키지 않는다.

제공 지표 (스펙 3장):
  - 이번 달 총 지출 / 이번 주 지출 / 카테고리별 지출
  - 지난달 대비 증감 / 최근 4주 평균 / 카테고리 증가율
  - 반복적인 소비 / 일회성 대규모 지출
  - 카드 결제 예정액 / 남은 예산 / 남은 기간 대비 예상 소비

card_bill_forecast, budget_status 는 가상 소비 시뮬레이션(STEP 13)에서도 재사용한다.
"""
from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from server.core import categories as C
from server.db.models import Transaction, UserProfile

# 배달 앱 탐지용 키워드 (카테고리는 식음료지만 '배달'을 따로 짚어야 함)
DELIVERY_KEYWORDS = ("배달의민족", "요기요", "쿠팡이츠", "배민")


# ------------------------------------------------------------------ 날짜 유틸
def add_months(d: date, n: int) -> date:
    """월 단위 이동. 말일 보정 포함."""
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def month_bounds(d: date) -> tuple[date, date]:
    first = d.replace(day=1)
    last = d.replace(day=calendar.monthrange(d.year, d.month)[1])
    return first, last


def _is_delivery(merchant: str) -> bool:
    return any(k in merchant for k in DELIVERY_KEYWORDS)


def _sum(txs: list[Transaction]) -> float:
    return float(sum(t.amount for t in txs))


def _expenses_in(txs: list[Transaction], start: date, end: date) -> list[Transaction]:
    return [t for t in txs if t.tx_type == C.EXPENSE and start <= t.tx_date <= end]


# ------------------------------------------------------------------ 결과 구조
@dataclass
class CategoryStat:
    category: str
    month_amount: float          # 이번 달 이 카테고리 지출
    share: float                 # 이번 달 지출 중 비중(0~1)
    week_amount: float           # 최근 7일
    baseline_week_avg: float     # 직전 4주 주간 평균
    increase_rate: float | None  # (week - baseline)/baseline, baseline=0이면 None


@dataclass
class AnalysisReport:
    today: date
    # --- 월 ---
    month_expense: float
    month_income: float
    last_month_expense: float
    last_month_income: float             # 지난달 동기간 소득 (소득 감소 탐지용)
    month_change_rate: float | None      # 지난달 대비 (동일 경과일 기준)
    income_change_rate: float | None     # 소득 증감 (동일 경과일 기준)
    # --- 주 ---
    week_expense: float                  # 최근 7일
    avg_weekly_expense: float            # 직전 4주 평균
    week_increase_rate: float | None
    # --- 예산/전망 ---
    monthly_budget: float
    remaining_budget: float              # 예산 - 이번달지출
    days_elapsed: int
    days_in_month: int
    projected_month_expense: float       # 현재 일평균 * 총일수
    projected_remaining_budget: float    # 예산 - 예상 월지출
    # --- 카드 ---
    upcoming_card_bill: float            # 다음 결제 예정액(이번 청구주기 신용카드 누적)
    next_billing_date: date
    # --- 상세 ---
    categories: list[CategoryStat] = field(default_factory=list)
    top_categories_increase: list[dict] = field(default_factory=list)  # 증가율 상위
    recurring: list[dict] = field(default_factory=list)                # 반복 소비
    subscriptions: list[dict] = field(default_factory=list)            # 구독
    large_one_time: list[dict] = field(default_factory=list)           # 일회성 대형
    delivery_week: float = 0.0           # 최근 7일 배달 지출
    delivery_baseline_week_avg: float = 0.0
    settlement: dict = field(default_factory=dict)  # 친구 송금 정산 요약
    category_merchants: dict = field(default_factory=dict)  # 카테고리별 이번 달 가맹점
    month_tx: list = field(default_factory=list)  # 이번 달 개별 거래 전체(LLM 상세답변용)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["today"] = self.today.isoformat()
        d["next_billing_date"] = self.next_billing_date.isoformat()
        return d


# ------------------------------------------------------------------ 개별 계산
def card_bill_forecast(
    txs: list[Transaction], today: date, billing_day: int
) -> tuple[float, date]:
    """다음 카드 결제 예정액과 결제일.

    모델(MVP): 다음 결제일 이전 청구주기 동안 발생한 '신용카드' 지출 누적액.
    (실제 카드사는 사용월/결제월 시차가 있으나, MVP는 직관적 모델을 쓰고 문서화한다.)
    """
    # 다음 결제일: today 이후(포함) 첫 billing_day
    last_day = calendar.monthrange(today.year, today.month)[1]
    bday = min(billing_day, last_day)
    if today.day <= bday:
        next_billing = today.replace(day=bday)
    else:
        next_billing = add_months(today.replace(day=1), 1)
        ld = calendar.monthrange(next_billing.year, next_billing.month)[1]
        next_billing = next_billing.replace(day=min(billing_day, ld))
    cycle_start = add_months(next_billing, -1)

    credit = [
        t for t in txs
        if t.tx_type == C.EXPENSE and t.payment_method == C.CREDIT
        and cycle_start <= t.tx_date <= today
    ]
    return _sum(credit), next_billing


def budget_status(
    txs: list[Transaction], today: date, monthly_budget: float
) -> dict:
    """남은 예산 + 남은 기간 대비 예상 소비."""
    first, _ = month_bounds(today)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = (today - first).days + 1

    month_exp = _sum(_expenses_in(txs, first, today))
    daily_rate = month_exp / days_elapsed if days_elapsed else 0.0
    projected = daily_rate * days_in_month

    return {
        "month_expense": month_exp,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "remaining_budget": monthly_budget - month_exp,
        "projected_month_expense": round(projected),
        "projected_remaining_budget": round(monthly_budget - projected),
    }


def _weekly_windows(txs: list[Transaction], today: date) -> tuple[float, float, list[float]]:
    """(이번주, 직전4주평균, 직전4주 각각) 반환. 주 = 7일 롤링 윈도우."""
    def window(k: int) -> float:  # k=0 이번주, k=1..4 직전
        end = today - timedelta(days=7 * k)
        start = end - timedelta(days=6)
        return _sum(_expenses_in(txs, start, end))

    this_week = window(0)
    prev = [window(k) for k in range(1, 5)]
    avg = sum(prev) / len(prev) if prev else 0.0
    return this_week, avg, prev


def _rate(current: float, base: float) -> float | None:
    if base <= 0:
        return None
    return (current - base) / base


# ------------------------------------------------------------------ 메인
def analyze(session: Session, user_id: int, today: date) -> AnalysisReport:
    txs = (
        session.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.tx_date.asc())
        .all()
    )
    profile = (
        session.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    )
    budget = profile.monthly_budget if profile else 600_000
    billing_day = profile.card_billing_day if profile else 14

    first, _ = month_bounds(today)

    # 월 지출/소득
    month_exps = _expenses_in(txs, first, today)
    month_expense = _sum(month_exps)
    month_income = _sum([
        t for t in txs if t.tx_type == C.INCOME and first <= t.tx_date <= today
    ])

    # 지난달 (동일 경과일 기준: 공정 비교)
    lm_first = add_months(first, -1)
    lm_same_day = add_months(today, -1)
    last_month_expense = _sum(_expenses_in(txs, lm_first, lm_same_day))
    # 정산 netting: 친구 송금(보냄−받음)을 실지출에 반영 → "내 몫만 지출"
    from server.services.transfers import settlement_netting
    net_now = settlement_netting(session, user_id, first, today)
    net_lm = settlement_netting(session, user_id, lm_first, lm_same_day)
    month_expense = max(0.0, month_expense + sum(net_now.values()))
    last_month_expense = max(0.0, last_month_expense + sum(net_lm.values()))
    month_change_rate = _rate(month_expense, last_month_expense)
    last_month_income = _sum([
        t for t in txs if t.tx_type == C.INCOME and lm_first <= t.tx_date <= lm_same_day
    ])
    income_change_rate = _rate(month_income, last_month_income)

    # 주간
    week_expense, avg_weekly, _prev = _weekly_windows(txs, today)
    week_increase_rate = _rate(week_expense, avg_weekly)

    # 예산/전망 + 카드 (정산 반영된 month_expense 사용)
    bs = budget_status(txs, today, budget)
    days_elapsed, days_in_month = bs["days_elapsed"], bs["days_in_month"]
    remaining_budget = budget - month_expense
    _daily = month_expense / days_elapsed if days_elapsed else 0.0
    projected_month = round(_daily * days_in_month)
    projected_remaining = round(budget - projected_month)
    card_bill, next_billing = card_bill_forecast(txs, today, billing_day)

    # 카테고리별 (정산 netting 반영: 친구 송금 보냄+ / 받음−)
    cat_month: dict[str, float] = defaultdict(float)
    for t in month_exps:
        cat_month[t.category] += t.amount
    for c, delta in net_now.items():
        cat_month[c] = max(0.0, cat_month.get(c, 0.0) + delta)

    # 카테고리별 이번 달 가맹점 (예: "여가에 뭐 썼어?" 답변용)
    _cat_merch: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in month_exps:
        _cat_merch[t.category][t.merchant] += t.amount
    category_merchants: dict[str, list[dict]] = {
        c: [{"merchant": m, "amount": round(a)}
            for m, a in sorted(mm.items(), key=lambda x: -x[1])[:6]]
        for c, mm in _cat_merch.items()
    }

    # 이번 달 개별 거래 전체 (LLM 이 '무슨 매장? 언제 얼마?' 상세 질문에 답하도록)
    month_tx = [
        {"date": t.tx_date.isoformat()[5:], "merchant": t.merchant, "category": t.category,
         "amount": round(t.amount), "type": t.tx_type, "dir": t.direction}
        for t in txs if first <= t.tx_date <= today
    ]
    month_tx.sort(key=lambda x: x["date"], reverse=True)

    # 송금 정산 요약(이번 달) + 미해결 사람 수
    from server.services.transfers import get_rules, person_key, person_transfers
    _rules = get_rules(session, user_id)
    _sent = _recv = 0.0
    _unresolved: set[str] = set()
    for t in person_transfers(session, user_id):
        k = person_key(t.merchant)
        if k not in _rules:
            _unresolved.add(k)
        elif first <= t.tx_date <= today:
            if t.direction == "out":
                _sent += t.amount
            else:
                _recv += t.amount
    settlement = {"sent": round(_sent), "received": round(_recv),
                  "net": round(_sent - _recv), "unresolved": len(_unresolved)}

    def cat_window(cat: str, k: int) -> float:
        end = today - timedelta(days=7 * k)
        start = end - timedelta(days=6)
        return _sum([t for t in _expenses_in(txs, start, end) if t.category == cat])

    categories: list[CategoryStat] = []
    for cat in sorted(cat_month, key=lambda c: -cat_month[c]):
        wk = cat_window(cat, 0)
        base = sum(cat_window(cat, k) for k in range(1, 5)) / 4
        categories.append(CategoryStat(
            category=cat,
            month_amount=round(cat_month[cat]),
            share=round(cat_month[cat] / month_expense, 3) if month_expense else 0.0,
            week_amount=round(wk),
            baseline_week_avg=round(base),
            increase_rate=_rate(wk, base),
        ))

    top_inc = sorted(
        [{"category": c.category, "week_amount": c.week_amount,
          "baseline_week_avg": c.baseline_week_avg, "increase_rate": c.increase_rate}
         for c in categories if c.increase_rate is not None and c.increase_rate > 0.3
         and c.week_amount >= 15_000],
        key=lambda x: -x["increase_rate"],
    )

    # 배달 (최근 7일 vs 직전 4주 평균)
    def delivery_window(k: int) -> float:
        end = today - timedelta(days=7 * k)
        start = end - timedelta(days=6)
        return _sum([t for t in _expenses_in(txs, start, end) if _is_delivery(t.merchant)])

    delivery_week = delivery_window(0)
    delivery_base = sum(delivery_window(k) for k in range(1, 5)) / 4

    # 구독 (이번 달)
    subs = [
        {"merchant": t.merchant, "amount": round(t.amount), "date": t.tx_date.isoformat()}
        for t in month_exps if t.category == C.SUBSCRIPTION
    ]

    # 반복 소비: 최근 30일 3회 이상 등장한 가맹점(정규화 없이 이름 기준, 소액)
    since = today - timedelta(days=29)
    recent = _expenses_in(txs, since, today)
    by_merchant: dict[str, list[Transaction]] = defaultdict(list)
    for t in recent:
        by_merchant[t.merchant].append(t)
    recurring = sorted(
        [{"merchant": m, "count": len(v), "total": round(_sum(v)),
          "avg": round(_sum(v) / len(v))}
         for m, v in by_merchant.items() if len(v) >= 3],
        key=lambda x: -x["total"],
    )

    # 일회성 대형 지출(이번 달): 5만원 이상 & 반복 아님
    recurring_names = {r["merchant"] for r in recurring}
    large = sorted(
        [{"merchant": t.merchant, "amount": round(t.amount),
          "category": t.category, "date": t.tx_date.isoformat(), "memo": t.memo}
         for t in month_exps if t.amount >= 50_000 and t.merchant not in recurring_names],
        key=lambda x: -x["amount"],
    )

    return AnalysisReport(
        today=today,
        month_expense=round(month_expense),
        month_income=round(month_income),
        last_month_expense=round(last_month_expense),
        last_month_income=round(last_month_income),
        month_change_rate=month_change_rate,
        income_change_rate=income_change_rate,
        week_expense=round(week_expense),
        avg_weekly_expense=round(avg_weekly),
        week_increase_rate=week_increase_rate,
        monthly_budget=round(budget),
        remaining_budget=round(remaining_budget),
        days_elapsed=days_elapsed,
        days_in_month=days_in_month,
        projected_month_expense=projected_month,
        projected_remaining_budget=projected_remaining,
        upcoming_card_bill=round(card_bill),
        next_billing_date=next_billing,
        categories=categories,
        top_categories_increase=top_inc,
        recurring=recurring,
        subscriptions=subs,
        large_one_time=large,
        delivery_week=round(delivery_week),
        delivery_baseline_week_avg=round(delivery_base),
        settlement=settlement,
        category_merchants=category_merchants,
        month_tx=month_tx,
    )
