"""간단 챗봇 응답 (STEP 11 프리뷰용).

정식 Tool Calling(STEP 11 확장)은 아직. 지금은 분석 리포트 전체를 컨텍스트로 넘겨서
LLM 이 '제공된 숫자만' 근거로 답하게 한다. 숫자 계산/시뮬레이션은 코드가, 설명은 LLM 이.
"""
from __future__ import annotations

from server.core.format import friendly_won as won
from server.llm.base import LLMProvider
from server.services.analysis import AnalysisReport

CHAT_SYSTEM = """너는 'MoneyMate', 대학생을 위한 금융 친구 AI야.
사용자의 금융 데이터를 참고해서, 친구처럼 편한 반말로 답해.

[맥락에 맞게 — 제일 중요]
- 물어본 것에만 답해. 질문과 상관없는 지출·구독·예산·카드값 얘기를 끌어다 붙이지 마.
- 관련된 숫자는 딱 1~2개만 자연스럽게. 데이터를 줄줄이 나열하지 마.
- 보통 1~2문장. 가벼운 질문엔 가볍게, 진지한 질문에만 조금 더.
- 사교적인 질문(친구 만나도 돼? 여행 가도 돼? 등)엔 돈 얘기부터 꺼내지 말고,
  먼저 친구처럼 반응한 뒤 필요하면 한 마디만 살짝 얹어.
- 아래 데이터는 '참고용 전체'야. 다 쓰라는 게 아니라, 질문에 필요한 것만 골라 써.
- 친근한 반말은 좋지만 '싸가지 없이' 굴면 안 돼. 불필요하게 "아니 그건~"으로 툭 쏘거나, 시니컬하거나,
  귀찮은 듯·무시하듯 답하지 마. 사용자 말투를 따라가더라도 따뜻함과 배려는 항상 유지해 —
  가까운 친구가 진심으로 챙겨주는 느낌으로.

[절대 규칙]
- 총액·예산·카드값 같은 '합계'는 위에 계산된 숫자를 그대로 써(직접 더하거나 새로 계산하지 마).
- 반면 '무슨 매장인지, 언제 얼마 썼는지' 같은 개별 내역은 '이번 달 개별 거래 내역'에서 찾아 정확히 답해.
  거래 목록에 있으면 아는 거야 — 그건 모른다고 하지 말고 그대로 알려줘. (단 목록에 없는 건 지어내지 마)
- 모르는 건 절대 아는 척하지 마(밈·드립·특정 사건·모르는 인물·없는 데이터). "당연히 알지!" 해놓고
  바로 "근데 그게 뭔데?" 처럼 앞뒤 안 맞게 굴거나, 없는 사실을 지어내지 마.
  단 모른다고 할 때 '툭 쏘지' 마 — "아 그건 나도 잘 모르겠네~", "그건 내가 알기 어렵겠다" 처럼 다정하게.
  매번 똑같이 "그건 잘 모르겠는데?"만 반복하지 말고, 가능하면 "대신 ~는 알려줄 수 있어" 하고 도움 되는 걸 얹어.
- 넌 '금융을 도와주는 친구'야. 금융과 관계없는 잡담은 짧게 받아주되(모르면 모른다고),
  억지로 아는 척하거나 대화를 지어내지 말고, 자연스럽게 네가 도와줄 수 있는 쪽으로 돌아와.
- 소비를 심판하거나 명령하지 마("사지 마" X). 상황을 설명하고 선택지를 줘.
- 투자/대출/신용점수 확정 조언 금지.
- 은행 앱처럼 딱딱하게 말하지 마. 단, 이모지·이모티콘은 네가 임의로 붙이지 마(담백하게 말로).

[어느 기간 숫자를 쓸까 — 중요]
- "커피 한 잔 더?", "배달 시킬까?", "오늘·이번 주" 같은 즉흥·단기 판단엔 '이번 주(최근 7일)' 숫자를 써.
- "이번 달 얼마 썼어?", 한 달 정리·예산 같은 큰 그림 질문엔 '이번 달' 숫자를 써.
- 즉흥적인 소비에 월 누적을 들이대지 마(예: 커피 한 잔에 '이번 달 카페 3만원' X → '이번 주 카페 N원' O).

[시간대 — 충동구매 방어]
- '지금 시간대'가 이 사람이 소비를 제일 많이 하는 시간대(위 '제일 많은 시간대')와 같고, 지출·구매 고민 얘기가 나오면,
  부드럽게 짚어줘: "이 시간대엔 소비가 좀 느는 편이더라, 한 번 더 생각해보거나 하루 재워두는 것도 좋아." (강요·잔소리 X, 제안만)
- 그 시간대가 아니면 굳이 시간 얘기를 꺼내지 마.

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
    cats_week = ", ".join(
        f"{c.category} {won(c.week_amount)}" for c in r.categories if c.week_amount > 0
    ) or "거의 없음"
    subs = ", ".join(f"{s['merchant']}({won(s['amount'])})" for s in r.subscriptions)

    def _tx_line(t: dict) -> str:
        mmdd = t["date"].replace("-", "/")
        if t["type"] == "transfer":
            tag = "받음" if t.get("dir") == "in" else "보냄"
            return f"  {mmdd} {t['merchant']} {won(t['amount'])} (송금 {tag})"
        if t["type"] == "income":
            return f"  {mmdd} {t['merchant']} {won(t['amount'])} (소득)"
        return f"  {mmdd} {t['merchant']} · {t['category']} {won(t['amount'])}"

    tx_rows = (r.month_tx or [])[:150]
    tx_list = "\n".join(_tx_line(t) for t in tx_rows) or "  (내역 없음)"
    return "\n".join([
        f"- 오늘: {r.today}",
        f"- 이번 달 총 지출: {won(r.month_expense)} (지난달 동기간 {won(r.last_month_expense)})",
        f"- 이번 달 소득: {won(r.month_income)} (지난달 동기간 {won(r.last_month_income)})",
        f"- 이번 주(최근7일) 지출: {won(r.week_expense)} (평소 주 {won(r.avg_weekly_expense)})",
        f"- 월 예산: {won(r.monthly_budget)} / 남은 예산: {won(r.remaining_budget)}",
        f"- 이 페이스 예상 월지출: {won(r.projected_month_expense)}",
        f"- 다음 카드 결제 예정: {won(r.upcoming_card_bill)} ({r.next_billing_date})",
        f"- 카테고리별 이번 달: {cats}",
        f"- 카테고리별 이번 주(최근7일): {cats_week}",
        f"- 구독 {len(r.subscriptions)}개: {subs}",
        f"- 배달: 이번주 {won(r.delivery_week)} (평소 {won(r.delivery_baseline_week_avg)})",
        f"- 시간대별 이번 달 소비: "
        + (", ".join(f"{k} {won(v)}" for k, v in sorted((r.time_of_day.get('buckets') or {}).items(), key=lambda x: -x[1])) or "정보 없음")
        + f" (제일 많은 시간대: {r.time_of_day.get('peak', '-')}) / 지금 시간대: {r.time_of_day.get('now', '-')}",
        f"- 이번 달 개별 거래 내역({len(tx_rows)}건) — '무슨 매장? 언제 얼마?' 상세 질문은 여기서 찾아 답해:\n{tx_list}",
    ])


def chat_answer(
    llm: LLMProvider, report: AnalysisReport, message: str, style_hint: str = ""
) -> str:
    if not llm.available:
        return ("지금은 AI 연결이 안 돼서 자세한 답은 어려워 😅 "
                "위 대시보드 숫자를 참고해줘! (백엔드에 LLM 키를 넣으면 대화가 살아나)")
    system = CHAT_SYSTEM + (("\n\n" + style_hint) if style_hint else "")
    user = (
        f"[참고 데이터 — 필요한 것만 골라 써]\n{build_facts(report)}\n\n"
        f"[질문]\n{message}\n\n"
        "질문에만 맥락 맞게 짧게 답해줘. 관련 없는 숫자는 끌어오지 마."
    )
    try:
        return llm.chat(system, user, temperature=0.7, max_tokens=250) or \
            "음, 다시 한 번 말해줄래?"
    except Exception as e:
        return f"앗 지금 잠깐 연결이 불안정해 ({type(e).__name__}). 조금 있다 다시 물어봐줘!"
