"""가상 소비 시뮬레이션 (STEP 13).

"30만원짜리 기타 사도 될까?" → 실제 결제 없이 재무 영향을 deterministic 코드로 계산.
계산은 여기서, 설명·선택지 제시는 LLM 코치가 담당(원칙 13-2/7). 절대 "사라/사지마" 강요 X.
"""
from __future__ import annotations

import re

from app.agents.coach import COACH_SYSTEM
from app.core.format import friendly_won as won
from app.llm.base import LLMProvider
from app.services.analysis import AnalysisReport

# 구매 후 하루 여유가 이 정도 미만이면 '빡빡'으로 본다.
_TIGHT_DAILY = 7_000

_BUY_HINTS = (
    "사도 될까", "사도돼", "사도 돼", "사도되", "살까", "사면", "사도 괜찮",
    "질러", "지름", "구매", "사볼까", "살만", "사는 거", "써도 될까", "써도 돼",
)


def is_purchase_question(text: str) -> bool:
    return any(k in text for k in _BUY_HINTS)


def parse_amount(text: str) -> int | None:
    """자연어에서 첫 금액 추출. '30만원', '20만 5천', '300,000원', '300000' 지원."""
    m = re.search(r"(\d[\d,]*)\s*만\s*(?:(\d[\d,]*)\s*천)?\s*원?", text)
    if m:
        man = int(m.group(1).replace(",", ""))
        cheon = int(m.group(2).replace(",", "")) if m.group(2) else 0
        return man * 10_000 + cheon * 1_000
    m = re.search(r"(\d[\d,]*)\s*천\s*원?", text)
    if m:
        return int(m.group(1).replace(",", "")) * 1_000
    m = re.search(r"(\d[\d,]{2,})\s*원?", text)  # 300000 / 300,000원
    if m:
        val = int(m.group(1).replace(",", ""))
        return val if val >= 1_000 else None
    return None


def simulate_purchase(
    report: AnalysisReport, amount: int, on_credit: bool = True
) -> dict:
    """구매 시 재무 영향을 계산한다(실제 저장 없음)."""
    days_left = max(report.days_in_month - report.days_elapsed, 1)

    before_remaining = report.remaining_budget
    after_remaining = before_remaining - amount
    before_card = report.upcoming_card_bill
    after_card = before_card + (amount if on_credit else 0)
    daily_after = after_remaining / days_left

    if after_remaining < 0:
        level = "over"      # 예산 초과
    elif daily_after < _TIGHT_DAILY:
        level = "tight"     # 가능하지만 빡빡
    else:
        level = "ok"        # 큰 무리 없음

    return {
        "amount": amount,
        "on_credit": on_credit,
        "days_left": days_left,
        "before_remaining": before_remaining,
        "after_remaining": after_remaining,
        "before_card": before_card,
        "after_card": after_card,
        "daily_after": round(daily_after),
        "level": level,
    }


def _fallback_message(sim: dict) -> str:
    lines = [
        f"{won(sim['amount'])}짜리 지금 산다고 치면,",
        f"이번 달 남은 생활비가 {won(sim['before_remaining'])} → "
        f"{won(sim['after_remaining'])}로 바뀌어.",
    ]
    if sim["on_credit"]:
        lines.append(f"다음 카드값도 {won(sim['after_card'])}까지 올라가고.")
    if sim["level"] == "over":
        lines.append("이번 달 예산은 넘기는 셈이라, 다음 달을 좀 당겨쓰는 느낌이 될 거야.")
    elif sim["level"] == "tight":
        lines.append(
            f"남은 {sim['days_left']}일 동안 하루 {won(sim['daily_after'])} 정도로 빡빡해져. "
            "못 살 건 아닌데 좀 타이트해."
        )
    else:
        lines.append(
            f"그래도 남은 기간 하루 {won(sim['daily_after'])} 정도는 쓸 수 있어서 큰 무리는 아니야."
        )
    lines.append("사는 것 자체가 안 될 건 아니고, 결정은 네 몫이야 🙂")
    return "\n".join(lines)


_SIM_NOTE = """
[지금은 '가상 소비 시뮬레이션' 상황이야]
- 실제 결제가 일어난 게 아니야. "만약 산다면" 을 계산해 본 거야.
- 아래 초안의 숫자·사실은 그대로 두고 말투만 자연스럽게 다듬어줘.
- 사용자가 사려는 물건을 자연스럽게 언급해도 좋아. 하지만 "사라/사지마"로 강요하지 말고,
  상황을 보여준 뒤 선택은 사용자에게 맡겨."""


def simulate_and_explain(
    llm: LLMProvider,
    report: AnalysisReport,
    amount: int,
    user_message: str,
    on_credit: bool = True,
) -> dict:
    sim = simulate_purchase(report, amount, on_credit)
    fallback = _fallback_message(sim)
    if not llm.available:
        return {"reply": fallback, "simulation": sim}
    facts = "\n".join([
        f"- 구매액: {won(sim['amount'])}",
        f"- 남은 생활비: {won(sim['before_remaining'])} → {won(sim['after_remaining'])}",
        f"- 다음 카드값: {won(sim['before_card'])} → {won(sim['after_card'])}",
        f"- 남은 {sim['days_left']}일, 구매 후 하루 여유 {won(sim['daily_after'])}",
        f"- 판정: {sim['level']}",
    ])
    prompt = (
        f'[사용자 질문]\n{user_message}\n\n'
        f"[계산 결과 — 이 숫자만 사용]\n{facts}\n\n"
        f"[규칙기반 초안]\n{fallback}\n\n"
        "위 초안을 MoneyMate 말투로 자연스럽게 다시 써줘."
    )
    try:
        out = llm.chat(COACH_SYSTEM + _SIM_NOTE, prompt, temperature=0.7, max_tokens=400)
        return {"reply": out or fallback, "simulation": sim}
    except Exception:
        return {"reply": fallback, "simulation": sim}
