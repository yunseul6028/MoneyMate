"""Agent 파이프라인 공용 타입 (STEP 9).

흐름: AnalysisReport → Analyst(Finding[]) → Critic(Verdict[]) → Proactive(ProactiveResult)
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- Critic 결정 ---
NO_INTERVENTION = "NO_INTERVENTION"  # 말 걸지 않음
ASK_CONTEXT = "ASK_CONTEXT"          # 맥락을 부드럽게 물어봄
WARN = "WARN"                        # 주의 환기
COACH = "COACH"                      # 상황 설명 + 선택지 제공

SPEAKABLE = {ASK_CONTEXT, WARN, COACH}


@dataclass
class Finding:
    """Analyst 가 탐지한 이상/변화 신호 한 건."""
    kind: str                    # delivery_spike | weekly_spike | card_bill_high | ...
    title: str                   # 사람이 읽는 요약
    severity: float              # 0~1, 얼마나 큰 변화인가
    confidence: float            # 0~1, 얼마나 확실한가
    driver: str | None = None    # 주 원인 (카테고리/가맹점 등)
    metrics: dict = field(default_factory=dict)  # 근거 숫자 (전부 deterministic 계산 결과)

    @property
    def score(self) -> float:
        return self.severity * self.confidence


@dataclass
class Verdict:
    """Critic 이 Finding 을 검증한 결과."""
    finding: Finding
    decision: str                # NO_INTERVENTION | ASK_CONTEXT | WARN | COACH
    reason: str                  # 왜 이 결정을 했는지 (투명성)
    confidence: float            # 검증 후 조정된 확신도

    @property
    def score(self) -> float:
        return self.finding.severity * self.confidence


@dataclass
class ProactiveResult:
    """'지금 먼저 말을 걸까?' 의 최종 판단."""
    should_speak: bool
    primary: Verdict | None = None          # 이번에 말 걸 핵심 1건
    supporting: list[dict] = field(default_factory=list)  # Coach 가 참고할 보조 사실
    fallback_message: str = ""              # LLM 없을 때 규칙기반 메시지 (STEP 10에서 대체)
    suppressed: list[str] = field(default_factory=list)   # 알림피로 방지로 눌린 항목들
    reason: str = ""                        # 말 안 걸기로 했다면 그 이유
