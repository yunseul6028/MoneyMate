"""Proactive Decision (STEP 9).

역할: 여러 신호를 조율해 '지금 먼저 말을 걸지', 건다면 '무엇을' 말할지 하나로 정한다.
원칙(13-5, 13-6): 매 거래마다 말 걸지 않는다. 알림 피로를 막는다.

핵심 규칙
  1. 알림 피로 방지: 최근 cooldown 기간에 같은 종류로 말했으면 다시 말하지 않음.
  2. 첫 접촉은 '질문' 하나로: ASK_CONTEXT 가 있으면 그것만 보내고 나머지는 미룬다
     (한 번에 여러 잔소리 X → 부담 최소화).
  3. 그 외엔 가장 중요한 COACH/WARN 1건 + 보조 사실 몇 개.

fallback_message 는 규칙기반 임시 문구. STEP 10 에서 LLM Coach 가 대체한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents.analyst import run_analyst
from app.agents.critic import run_critic
from app.agents.types import (
    ASK_CONTEXT,
    SPEAKABLE,
    ProactiveResult,
    Verdict,
)
from app.db.models import AgentEvent
from app.services.analysis import AnalysisReport

# 주제별 중요도(현금흐름 > 잔소리). 최종 순위 = score × weight.
TOPIC_WEIGHT: dict[str, float] = {
    "card_bill_high": 1.3,   # 다음 결제액 (현금흐름)
    "budget_overrun": 1.2,
    "delivery_spike": 1.0,
    "weekly_spike": 0.9,
    "income_drop": 0.5,
    "subscription_creep": 0.6,  # 급하지 않은 점검거리
}


def _weighted(v: Verdict) -> float:
    return v.score * TOPIC_WEIGHT.get(v.finding.kind, 1.0)


def _spoke_recently(session: Session, user_id: int, now: datetime, hours: int) -> bool:
    since = now - timedelta(hours=hours)
    return (
        session.query(AgentEvent.id)
        .filter(AgentEvent.user_id == user_id, AgentEvent.created_at >= since)
        .first()
        is not None
    )


def _recent_triggers(session: Session, user_id: int, now: datetime, cooldown_days: int) -> set[str]:
    since = now - timedelta(days=cooldown_days)
    rows = (
        session.query(AgentEvent.trigger)
        .filter(AgentEvent.user_id == user_id, AgentEvent.created_at >= since)
        .all()
    )
    return {r[0] for r in rows}


def _won(n: float) -> str:
    return f"{n:,.0f}원"


def _build_message(primary: Verdict, report: AnalysisReport, supporting: list[dict]) -> str:
    f = primary.finding
    m = f.metrics
    if f.kind == "delivery_spike":
        return (
            f"야 잠깐ㅋㅋ 이번 주 소비가 평소보다 좀 많아.\n"
            f"평소엔 주 {_won(report.avg_weekly_expense)} 정도 쓰는데 이번 주엔 {_won(report.week_expense)} 썼어.\n"
            f"특히 배달이 {_won(m['week'])}으로 확 늘었는데, 이번 주에 무슨 일 있었어?"
        )
    if f.kind == "weekly_spike":
        return (
            f"이번 주에 {_won(report.week_expense)} 썼는데 평소({_won(report.avg_weekly_expense)})보다 좀 많네.\n"
            f"무슨 일 있었어? 일회성이면 크게 걱정 안 해도 돼."
        )
    if f.kind == "card_bill_high":
        lines = [
            f"다음 카드 결제 예정액이 {_won(m['card_bill'])} 정도야 ({m['next_billing_date']} 결제).",
        ]
        for s in supporting:
            lines.append(s["line"])
        lines.append("당장 못 낼 정도는 아니지만, 남은 기간엔 조금만 신경 쓰면 좋을 것 같아.")
        return "\n".join(lines)
    if f.kind == "budget_overrun":
        daily = max(0, round(report.projected_remaining_budget / max(report.days_in_month - report.days_elapsed, 1)))
        return (
            f"이 페이스로 가면 이번 달 예산을 {_won(m['overrun'])} 정도 넘길 것 같아.\n"
            f"남은 {report.days_in_month - report.days_elapsed}일 동안 조금만 조절하면 충분히 맞출 수 있어."
        )
    if f.kind == "subscription_creep":
        items = ", ".join(f"{i['merchant']}({_won(i['amount'])})" for i in m["items"])
        return (
            f"구독이 지금 {m['count']}개, 월 {_won(m['total'])} 나가고 있어.\n"
            f"{items}\n안 쓰는 거 있으면 정리해도 좋을 듯?"
        )
    return f.title


def decide(
    session: Session,
    user_id: int,
    report: AnalysisReport,
    acknowledged: set[str] | None = None,
    now: datetime | None = None,
    cooldown_days: int = 3,
    global_cooldown_hours: int = 20,
) -> ProactiveResult:
    acknowledged = acknowledged or set()
    now = now or datetime.now(timezone.utc)

    findings = run_analyst(report)
    verdicts = [run_critic(f, report, acknowledged) for f in findings]
    speakable = [v for v in verdicts if v.decision in SPEAKABLE]

    # 0) 전역 쿨다운: 최근에 이미 '먼저' 말을 걸었으면 조용히 한다(알림 피로).
    #    단, 사용자가 대화 중(acknowledged 존재)이면 후속 응답이므로 적용하지 않는다.
    if not acknowledged and _spoke_recently(session, user_id, now, global_cooldown_hours):
        return ProactiveResult(should_speak=False,
                               reason="최근 이미 먼저 말을 걸었음(전역 알림 피로 방지)")

    # 1) 같은 주제 반복 방지(주제별 쿨다운)
    recent = _recent_triggers(session, user_id, now, cooldown_days)
    fresh = [v for v in speakable if v.finding.kind not in recent]
    suppressed = [v.finding.kind for v in speakable if v.finding.kind in recent]

    if not fresh:
        reason = "말 걸 만한 새 신호 없음" if not speakable else "최근 이미 안내함(알림 피로 방지)"
        return ProactiveResult(should_speak=False, suppressed=suppressed, reason=reason)

    # 2) 첫 접촉은 질문 하나로
    asks = [v for v in fresh if v.decision == ASK_CONTEXT]
    if asks:
        primary = max(asks, key=lambda v: v.score)
        others = [v.finding.kind for v in fresh if v is not primary]
        msg = _build_message(primary, report, [])
        return ProactiveResult(
            should_speak=True, primary=primary, supporting=[],
            fallback_message=msg, suppressed=suppressed + others,
            reason="맥락을 먼저 물어봄(첫 접촉은 질문 1건)",
        )

    # 3) 가장 중요한 COACH/WARN 1건 + 보조 사실 (주제 가중치 반영)
    primary = max(fresh, key=_weighted)
    supporting = _supporting_facts(report, findings, primary)
    msg = _build_message(primary, report, supporting)
    others = [v.finding.kind for v in fresh if v is not primary]
    return ProactiveResult(
        should_speak=True, primary=primary, supporting=supporting,
        fallback_message=msg, suppressed=suppressed + others,
        reason="핵심 1건 코칭",
    )


def _supporting_facts(report: AnalysisReport, findings: list, primary: Verdict) -> list[dict]:
    """Coach 가 참고할 보조 사실. (소득 감소 등 맥락을 함께 전달)"""
    facts: list[dict] = []
    kinds = {f.kind for f in findings}
    if primary.finding.kind in ("card_bill_high", "budget_overrun"):
        if "income_drop" in kinds:
            inc = next(f for f in findings if f.kind == "income_drop")
            facts.append({
                "key": "income_drop",
                "line": f"이번 달은 소득도 {_won(inc.metrics['income'])}으로 지난달보다 줄어서 여유가 빡빡해.",
                "metrics": inc.metrics,
            })
        facts.append({
            "key": "remaining_budget",
            "line": f"이번 달 예산은 {_won(report.remaining_budget)} 남았어.",
            "metrics": {"remaining_budget": report.remaining_budget},
        })
    return facts


def record_event(
    session: Session, user_id: int, result: ProactiveResult, now: datetime | None = None
) -> AgentEvent | None:
    """말을 걸기로 한 판단을 기록(알림 피로 방지의 근거가 됨)."""
    if not result.should_speak or result.primary is None:
        return None
    ev = AgentEvent(
        user_id=user_id,
        decision=result.primary.decision,
        trigger=result.primary.finding.kind,
        message=result.fallback_message,
        analysis={
            "finding": result.primary.finding.title,
            "reason": result.primary.reason,
            "metrics": result.primary.finding.metrics,
            "supporting": [s["key"] for s in result.supporting],
        },
    )
    if now is not None:
        ev.created_at = now
    session.add(ev)
    session.flush()
    return ev
