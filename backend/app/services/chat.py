"""간단 챗봇 응답 (STEP 11 프리뷰용).

정식 Tool Calling(STEP 11 확장)은 아직. 지금은 분석 리포트 전체를 컨텍스트로 넘겨서
LLM 이 '제공된 숫자만' 근거로 답하게 한다. 숫자 계산/시뮬레이션은 코드가, 설명은 LLM 이.
"""
from __future__ import annotations

from app.core.format import friendly_won as won
from app.llm.base import LLMProvider
from app.services.analysis import AnalysisReport

CHAT_SYSTEM = """너는 'MoneyMate', 대학생을 위한 금융 친구 AI야.
사용자의 금융 데이터를 참고해서, 친구처럼 편한 반말로 답해.

[맥락에 맞게 — 제일 중요]
- 물어본 것에만 답해. 질문과 상관없는 지출·구독·예산·카드값 얘기를 끌어다 붙이지 마.
- 관련된 숫자는 딱 1~2개만 자연스럽게. 데이터를 줄줄이 나열하지 마.
- 보통 1~2문장. 가벼운 질문엔 가볍게, 진지한 질문에만 조금 더.
- 사교적인 질문(친구 만나도 돼? 여행 가도 돼? 등)엔 돈 얘기부터 꺼내지 말고,
  먼저 친구처럼 반응한 뒤 필요하면 한 마디만 살짝 얹어.
- 아래 데이터는 '참고용 전체'야. 다 쓰라는 게 아니라, 질문에 필요한 것만 골라 써.

[절대 규칙]
- 아래 제공된 숫자만 사용해. 새로 계산하거나 지어내지 마. 모르면 "그건 아직 정확히 모르겠어"라고 해.
- 소비를 심판하거나 명령하지 마("사지 마" X). 상황을 설명하고 선택지를 줘.
- 투자/대출/신용점수 확정 조언 금지.
- 은행 앱처럼 딱딱하게 말하지 마. 이모지는 최대 1개.

[비용의 시간 단위 — 중요]
- 구독은 매달 고정으로 빠져나가는 '고정비'야. "이번 주에 구독을 줄이자"처럼 주 단위로 말하지 마.
  구독 점검은 "다음 결제 전에 안 쓰는 거 한 번 정리해볼까?"처럼 월 단위 관점으로 얘기해.
- 주/일 단위로 바로 조절할 수 있는 건 배달·카페 같은 '변동비'야. 단기 조절 얘기는 여기에 붙여.

[금액 표기]
- 아래 데이터의 금액은 이미 '약 32만원', '7만 6천원'처럼 반올림돼 있어. 그 표현을 그대로 써.
- "324,207원"처럼 원 단위 숫자를 전부 나열하지 마. 대화에선 '약'을 붙여 대략적으로 말해도 좋아."""


def build_facts(report: AnalysisReport) -> str:
    r = report
    cats = ", ".join(f"{c.category} {won(c.month_amount)}" for c in r.categories)
    subs = ", ".join(f"{s['merchant']}({won(s['amount'])})" for s in r.subscriptions)
    return "\n".join([
        f"- 오늘: {r.today}",
        f"- 이번 달 총 지출: {won(r.month_expense)} (지난달 동기간 {won(r.last_month_expense)})",
        f"- 이번 달 소득: {won(r.month_income)} (지난달 동기간 {won(r.last_month_income)})",
        f"- 이번 주 지출: {won(r.week_expense)} (평소 주 {won(r.avg_weekly_expense)})",
        f"- 월 예산: {won(r.monthly_budget)} / 남은 예산: {won(r.remaining_budget)}",
        f"- 이 페이스 예상 월지출: {won(r.projected_month_expense)}",
        f"- 다음 카드 결제 예정: {won(r.upcoming_card_bill)} ({r.next_billing_date})",
        f"- 카테고리별 이번 달: {cats}",
        f"- 구독 {len(r.subscriptions)}개: {subs}",
        f"- 배달: 이번주 {won(r.delivery_week)} (평소 {won(r.delivery_baseline_week_avg)})",
    ])


def chat_answer(llm: LLMProvider, report: AnalysisReport, message: str) -> str:
    if not llm.available:
        return ("지금은 AI 연결이 안 돼서 자세한 답은 어려워 😅 "
                "위 대시보드 숫자를 참고해줘! (백엔드에 LLM 키를 넣으면 대화가 살아나)")
    user = (
        f"[참고 데이터 — 필요한 것만 골라 써]\n{build_facts(report)}\n\n"
        f"[질문]\n{message}\n\n"
        "질문에만 맥락 맞게 짧게 답해줘. 관련 없는 숫자는 끌어오지 마."
    )
    try:
        return llm.chat(CHAT_SYSTEM, user, temperature=0.7, max_tokens=250) or \
            "음, 다시 한 번 말해줄래?"
    except Exception as e:
        return f"앗 지금 잠깐 연결이 불안정해 ({type(e).__name__}). 조금 있다 다시 물어봐줘!"
