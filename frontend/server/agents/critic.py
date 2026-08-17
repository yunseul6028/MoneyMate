"""Risk / Critic Agent (STEP 9).

역할: Analyst 의 각 Finding 을 '정말 개입이 필요한가' 관점에서 검증한다.
  - 일회성 지출인가? (여행/등록금/교재/의료 대형결제로 설명되나)
  - 사용자가 이미 설명한 이벤트인가? (acknowledged)
  - 실제 금융 위험으로 이어지나?
→ NO_INTERVENTION / ASK_CONTEXT / WARN / COACH

원칙(13-7): 소비를 도덕적으로 평가하지 않는다. 판단이 애매하면 '경고'가 아니라 '질문'.
Critic 은 각 Finding 을 독립적으로 본다. 여러 신호 간 조율/알림피로는 Proactive 담당.
"""
from __future__ import annotations

from server.agents.types import (
    ASK_CONTEXT,
    COACH,
    NO_INTERVENTION,
    Finding,
    Verdict,
)
from server.services.analysis import AnalysisReport

# 사용자 발화 → 맥락 토큰 (Chat 에서 재사용). 매우 단순한 키워드 매핑(LLM 전 단계).
_ACK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "exam": ("시험", "시험기간", "기말", "중간고사", "과제"),
    "travel": ("여행", "여행지", "놀러", "부산", "제주"),
    "tuition": ("등록금", "학비"),
    "textbook": ("교재", "책값", "전공책"),
    "event": ("생일", "기념일", "모임", "회식"),
    "medical": ("병원", "치료", "아파", "약값"),
}

# 어떤 ack 토큰이 어떤 finding 을 '설명'하는가
_EXPLAINS: dict[str, set[str]] = {
    "delivery_spike": {"exam"},
    "weekly_spike": {"exam", "travel", "tuition", "textbook", "event", "medical"},
    "budget_overrun": {"travel", "tuition", "exam"},
}

# 대형 일회성 지출로 자연스레 설명되는 카테고리
_ONE_TIME_CATEGORIES = {"여행", "교육", "의료", "여가"}


def infer_ack_tokens(text: str) -> set[str]:
    """사용자 답변에서 맥락 토큰 추출. 예: '시험기간이라...' → {'exam'}."""
    found = set()
    for token, kws in _ACK_KEYWORDS.items():
        if any(kw in text for kw in kws):
            found.add(token)
    return found


def _explained_by_one_time(report: AnalysisReport) -> bool:
    """이번 달 대형 일회성 지출(여행/교육 등)이 있는가."""
    return any(l["category"] in _ONE_TIME_CATEGORIES for l in report.large_one_time)


def run_critic(
    finding: Finding, report: AnalysisReport, acknowledged: set[str]
) -> Verdict:
    kind = finding.kind
    explains = _EXPLAINS.get(kind, set())

    # 사용자가 이미 설명한 이벤트 → 개입하지 않음
    if acknowledged & explains:
        tok = ", ".join(sorted(acknowledged & explains))
        return Verdict(finding, NO_INTERVENTION,
                       f"사용자가 이미 설명함({tok}) → 일시적/정상으로 간주", 0.9)

    if kind == "delivery_spike":
        # 판단하지 않고 먼저 맥락을 물어본다.
        return Verdict(finding, ASK_CONTEXT,
                       "배달이 크게 늘었으나 원인 불명 → 경고 대신 맥락 질문", finding.confidence)

    if kind == "weekly_spike":
        if _explained_by_one_time(report):
            return Verdict(finding, NO_INTERVENTION,
                           "대형 일회성 지출로 설명됨 → 정상적인 일시 증가", 0.8)
        # 배달이 주 원인이면 delivery_spike 가 대표 → 여기선 중복 회피
        if finding.driver == "식음료" and report.delivery_week >= 50_000:
            return Verdict(finding, NO_INTERVENTION,
                           "배달 급증(별도 신호)이 주 원인 → 중복 회피", 0.6)
        return Verdict(finding, ASK_CONTEXT,
                       "원인 불명 지출 급증 → 맥락 질문", finding.confidence)

    if kind == "card_bill_high":
        # 사실 기반 정보 제공. 심판이 아니라 상황 설명 + 선택지.
        return Verdict(finding, COACH,
                       "다음 결제액이 예산 대비 큼 → 상황 설명과 선택지 제공", finding.confidence)

    if kind == "budget_overrun":
        # 전망은 최근 급증에 취약 → 급증이 일회성으로 설명될 땐 신뢰 낮춤
        if _explained_by_one_time(report):
            return Verdict(finding, NO_INTERVENTION,
                           "예산초과 전망이 일회성 지출에서 비롯 → 과잉경고 회피", 0.4)
        return Verdict(finding, COACH,
                       "현재 페이스 유지 시 예산 초과 가능 → 부드러운 안내", finding.confidence)

    if kind == "subscription_creep":
        return Verdict(finding, COACH,
                       "구독이 늘어 고정비 부담 → 점검 제안(선택지)", finding.confidence)

    if kind == "income_drop":
        # 소득 감소 자체는 경고 대상이 아님(맥락). Proactive 가 예산 코칭의 근거로 활용.
        return Verdict(finding, NO_INTERVENTION,
                       "소득 감소는 맥락 정보 → 단독 경고하지 않고 예산 코칭에 반영", finding.confidence)

    return Verdict(finding, NO_INTERVENTION, "기본값", finding.confidence)
