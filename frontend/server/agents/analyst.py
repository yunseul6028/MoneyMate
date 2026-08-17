"""Financial Analyst (STEP 9).

역할: 분석 리포트(deterministic 숫자)에서 '이상/변화 신호(Finding)'를 뽑아낸다.
여기서 새로 계산하지 않는다 — analysis.py 가 만든 숫자를 해석해 신호로 변환할 뿐.
판단(개입 여부)은 하지 않는다. 그건 Critic 의 몫.
"""
from __future__ import annotations

from server.agents.types import Finding
from server.services.analysis import AnalysisReport


def _band(x: float, lo: float, hi: float) -> float:
    """[lo,hi] 구간을 0~1 로 정규화(clamp)."""
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def run_analyst(r: AnalysisReport) -> list[Finding]:
    findings: list[Finding] = []

    # 1) 배달 급증 (가장 구체적인 신호)
    if r.delivery_week >= 50_000 and r.delivery_week >= 2 * max(r.delivery_baseline_week_avg, 1):
        ratio = r.delivery_week / max(r.delivery_baseline_week_avg, 1)
        findings.append(Finding(
            kind="delivery_spike",
            title=f"배달 지출 급증 (이번주 {r.delivery_week:,}원 / 평소 {r.delivery_baseline_week_avg:,}원)",
            severity=_band(ratio, 2.0, 6.0),
            confidence=0.9,
            driver="배달",
            metrics={"week": r.delivery_week, "baseline": r.delivery_baseline_week_avg,
                     "ratio": round(ratio, 2)},
        ))

    # 2) 주간 지출 급증 (전체)
    if r.week_increase_rate is not None and r.week_increase_rate >= 0.4 \
            and (r.week_expense - r.avg_weekly_expense) >= 50_000:
        # 주 원인 카테고리: 증가액(주간-평소)이 가장 큰 것
        driver = None
        if r.top_categories_increase:
            driver = max(
                r.top_categories_increase,
                key=lambda c: c["week_amount"] - c["baseline_week_avg"],
            )["category"]
        findings.append(Finding(
            kind="weekly_spike",
            title=f"이번 주 지출 {r.week_expense:,}원 (평소 {r.avg_weekly_expense:,}원, "
                  f"+{r.week_increase_rate*100:.0f}%)",
            severity=_band(r.week_increase_rate, 0.4, 1.5),
            confidence=0.85,
            driver=driver,
            metrics={"week": r.week_expense, "baseline": r.avg_weekly_expense,
                     "increase_rate": round(r.week_increase_rate, 2)},
        ))

    # 3) 다음 카드 결제액 과다 (예산 대비)
    if r.monthly_budget > 0 and r.upcoming_card_bill >= 0.9 * r.monthly_budget:
        ratio = r.upcoming_card_bill / r.monthly_budget
        findings.append(Finding(
            kind="card_bill_high",
            title=f"다음 카드 결제 예정액 {r.upcoming_card_bill:,}원 "
                  f"(예산 {r.monthly_budget:,}원의 {ratio*100:.0f}%)",
            severity=_band(ratio, 0.9, 1.6),
            confidence=0.95,
            driver="신용카드",
            metrics={"card_bill": r.upcoming_card_bill, "budget": r.monthly_budget,
                     "next_billing_date": r.next_billing_date.isoformat()},
        ))

    # 4) 예산 초과 전망 (남은 기간 대비 예상 소비)
    if r.projected_remaining_budget < -30_000:
        over = -r.projected_remaining_budget
        findings.append(Finding(
            kind="budget_overrun",
            title=f"이 페이스면 예산 {over:,}원 초과 전망 "
                  f"(예상 월지출 {r.projected_month_expense:,}원)",
            severity=_band(over / max(r.monthly_budget, 1), 0.05, 0.8),
            # 전망은 최근 급증에 영향을 크게 받아 불확실 → 확신도 낮게
            confidence=0.5,
            driver="예산",
            metrics={"projected_month": r.projected_month_expense,
                     "overrun": over, "budget": r.monthly_budget},
        ))

    # 5) 구독 증가
    subs_total = sum(s["amount"] for s in r.subscriptions)
    if len(r.subscriptions) >= 4 or subs_total >= 50_000:
        findings.append(Finding(
            kind="subscription_creep",
            title=f"구독 {len(r.subscriptions)}개 · 월 {subs_total:,}원",
            severity=_band(subs_total, 40_000, 120_000),
            confidence=0.8,
            driver="구독",
            metrics={"count": len(r.subscriptions), "total": subs_total,
                     "items": r.subscriptions},
        ))

    # 6) 소득 감소 (동일 경과일 기준)
    if r.income_change_rate is not None and r.income_change_rate <= -0.25 \
            and r.last_month_income >= 100_000:
        drop = r.last_month_income - r.month_income
        findings.append(Finding(
            kind="income_drop",
            title=f"이번 달 소득 {r.month_income:,}원 (지난달 동기간 {r.last_month_income:,}원, "
                  f"{r.income_change_rate*100:.0f}%)",
            severity=_band(-r.income_change_rate, 0.25, 0.8),
            confidence=0.7,
            driver="소득",
            metrics={"income": r.month_income, "last": r.last_month_income, "drop": drop},
        ))

    return findings
