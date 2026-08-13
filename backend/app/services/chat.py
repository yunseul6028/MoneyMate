"""간단 챗봇 응답 (STEP 11 프리뷰용).

정식 Tool Calling(STEP 11 확장)은 아직. 지금은 분석 리포트 전체를 컨텍스트로 넘겨서
LLM 이 '제공된 숫자만' 근거로 답하게 한다. 숫자 계산/시뮬레이션은 코드가, 설명은 LLM 이.
"""
from __future__ import annotations

from app.llm.base import LLMProvider
from app.services.analysis import AnalysisReport

CHAT_SYSTEM = """너는 'MoneyMate', 대학생을 위한 금융 친구 AI야.
사용자의 금융 데이터를 바탕으로 질문에 친구처럼 편한 반말로 짧게(2~4문장) 답해.

[절대 규칙]
- 아래 제공된 숫자만 사용해. 새로 계산하거나 지어내지 마. 모르면 "그건 아직 정확히 모르겠어"라고 해.
- 소비를 심판하거나 명령하지 마("사지 마" X). 상황을 설명하고 선택지를 줘.
- 투자/대출/신용점수 확정 조언 금지.
- 은행 앱처럼 딱딱하게 말하지 마. 이모지는 최대 1개."""


def build_facts(report: AnalysisReport) -> str:
    r = report
    cats = ", ".join(f"{c.category} {c.month_amount:,}원" for c in r.categories)
    subs = ", ".join(f"{s['merchant']}({s['amount']:,}원)" for s in r.subscriptions)
    return "\n".join([
        f"- 오늘: {r.today}",
        f"- 이번 달 총 지출: {r.month_expense:,}원 (지난달 동기간 {r.last_month_expense:,}원)",
        f"- 이번 달 소득: {r.month_income:,}원 (지난달 동기간 {r.last_month_income:,}원)",
        f"- 이번 주 지출: {r.week_expense:,}원 (평소 주 {r.avg_weekly_expense:,}원)",
        f"- 월 예산: {r.monthly_budget:,}원 / 남은 예산: {r.remaining_budget:,}원",
        f"- 이 페이스 예상 월지출: {r.projected_month_expense:,}원",
        f"- 다음 카드 결제 예정: {r.upcoming_card_bill:,}원 ({r.next_billing_date})",
        f"- 카테고리별 이번 달: {cats}",
        f"- 구독 {len(r.subscriptions)}개: {subs}",
        f"- 배달: 이번주 {r.delivery_week:,}원 (평소 {r.delivery_baseline_week_avg:,}원)",
    ])


def chat_answer(llm: LLMProvider, report: AnalysisReport, message: str) -> str:
    if not llm.available:
        return ("지금은 AI 연결이 안 돼서 자세한 답은 어려워 😅 "
                "위 대시보드 숫자를 참고해줘! (백엔드에 LLM 키를 넣으면 대화가 살아나)")
    user = (
        f"[사용자 금융 데이터]\n{build_facts(report)}\n\n"
        f"[질문]\n{message}\n\n"
        "위 데이터의 숫자만 써서 친구처럼 답해줘."
    )
    try:
        return llm.chat(CHAT_SYSTEM, user, temperature=0.7, max_tokens=400) or \
            "음, 다시 한 번 말해줄래?"
    except Exception as e:
        return f"앗 지금 잠깐 연결이 불안정해 ({type(e).__name__}). 조금 있다 다시 물어봐줘!"
