"""Financial Coach (STEP 10) — LLM 이 '검증된 판단 + 확정된 숫자'를 친근한 말로 옮긴다.

핵심 안전장치:
  - 숫자는 이미 코드가 계산해 fallback_message/facts 에 박혀 있다.
  - LLM 에게는 "숫자를 바꾸거나 새로 만들지 말고 말투만 다듬어라"고 강하게 지시한다.
  - LLM 이 없으면(available=False) 규칙기반 fallback_message 를 그대로 쓴다.
원칙 13-2/3/4/7/8 준수: 계산 금지, 도덕적 심판 금지, 확정적 금융조언 금지.
"""
from __future__ import annotations

from app.agents.types import ASK_CONTEXT, ProactiveResult, Verdict
from app.llm.base import LLMProvider
from app.services.analysis import AnalysisReport

COACH_SYSTEM = """너는 'MoneyMate'라는, 대학생을 위한 금융 친구 AI야.
너의 목표는 사용자가 스스로 판단하도록 돕는 거지, 소비를 통제하거나 심판하는 게 아니야.

[말투]
- 친한 친구처럼 편한 반말. 가끔 'ㅋㅋ' 정도는 OK. 이모지는 최대 1개.
- 짧고 담백하게. 2~4문장.
- 은행 앱처럼 딱딱한 말투 금지. ("귀하의 소비가 예산을 초과했습니다" 같은 말 X)

[절대 규칙]
- 숫자·금액·날짜는 아래 제공된 값만 사용해. 새로 계산하거나 바꾸거나 지어내지 마.
- "사지 마", "이건 낭비야" 같은 명령·도덕적 심판 금지. 상황을 설명하고 선택지를 줘.
- 투자/대출/신용점수에 대한 확정적 조언 금지.
- 결정유형이 ASK_CONTEXT 면 반드시 질문으로 끝내(맥락을 물어봐).

[비용의 시간 단위 — 중요]
- 구독은 매달 고정으로 나가는 '고정비'야. "이번 주에 구독을 줄이자"처럼 주 단위로 말하지 마.
  구독 얘기는 "다음 결제 전에 안 쓰는 거 정리해볼까?"처럼 월 단위 관점으로 해.
- 배달·카페처럼 주/일 단위로 바로 조절되는 건 '변동비'. 단기 조절 제안은 여기에만 붙여.

[금액 표기]
- 초안의 금액은 이미 '약 32만원', '7만 6천원'처럼 반올림돼 있어. 그 표현을 그대로 써.
- "324,207원"처럼 원 단위 숫자를 전부 나열하지 마."""


def _facts_block(result: ProactiveResult) -> str:
    # 원 단위 원시 metrics 는 넣지 않는다(초안·보조문장에 이미 친근한 금액으로 들어있음).
    lines = [s["line"] for s in result.supporting]
    return "\n".join(lines) if lines else "- (초안의 숫자를 그대로 사용)"


def _build_user_prompt(result: ProactiveResult) -> str:
    decision = result.primary.decision if result.primary else "COACH"
    return (
        f"[결정유형] {decision}\n"
        f"[말 거는 이유] {result.reason}\n\n"
        f"[사용할 수 있는 숫자 — 이 값만 쓰고 새로 계산하지 마]\n{_facts_block(result)}\n\n"
        f"[규칙기반 초안 — 숫자·사실은 그대로 두고 말투만 더 자연스럽게 다듬어줘]\n"
        f"{result.fallback_message}\n\n"
        f"위 초안을 MoneyMate 말투로 자연스럽게 다시 써줘. 숫자는 절대 바꾸지 마."
    )


def speak(llm: LLMProvider, result: ProactiveResult, report: AnalysisReport) -> str:
    """proactive 결과를 사용자에게 건넬 최종 메시지로 변환."""
    if not result.should_speak:
        return ""
    if not llm.available:
        return result.fallback_message  # 키 없음 → 규칙기반 그대로
    try:
        temp = 0.8 if (result.primary and result.primary.decision == ASK_CONTEXT) else 0.7
        out = llm.chat(COACH_SYSTEM, _build_user_prompt(result), temperature=temp, max_tokens=400)
        return out or result.fallback_message
    except Exception as e:  # 네트워크/키 오류 → 안전하게 fallback
        return result.fallback_message + f"\n\n(LLM 호출 실패로 기본 문구 사용: {type(e).__name__})"
