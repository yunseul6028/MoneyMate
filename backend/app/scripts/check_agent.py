"""Proactive Agent 파이프라인 검증 (STEP 9).  python -m app.scripts.check_agent

스펙의 데모 흐름을 그대로 재현:
  ① 에이전트가 먼저 배달 급증을 감지하고 '무슨 일 있었어?' 라고 물음(ASK_CONTEXT)
  ② 알림 피로 방지: 곧바로 다시 돌리면 같은 얘기 반복 안 함
  ③ 사용자가 '시험기간'이라 답하면 → 그 신호는 NO_INTERVENTION,
     대신 카드 결제/예산을 부드럽게 코칭(COACH)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agents.analyst import run_analyst
from app.agents.critic import infer_ack_tokens, run_critic
from app.agents.proactive import decide, record_event
from app.core import clock
from app.db.database import init_db, session_scope
from app.providers.mock_provider import MockFinancialDataProvider
from app.services.analysis import analyze


def _line():
    print("─" * 64)


def run() -> None:
    init_db()
    provider = MockFinancialDataProvider()
    with session_scope() as s:
        provider.ensure_global_rules(s)
        user = provider.ensure_demo_user(s)
        provider.sync_transactions(s, user.id)
        uid = user.id

    now = clock.now()

    # --- Analyst / Critic 원시 출력 ---
    with session_scope() as s:
        report = analyze(s, uid, clock.today())
        findings = run_analyst(report)
        print("=== Financial Analyst: 탐지된 신호 ===")
        for f in findings:
            print(f"  • [{f.kind}] {f.title}")
            print(f"      severity={f.severity:.2f} confidence={f.confidence:.2f} driver={f.driver}")
        print("\n=== Risk/Critic: 검증 결과 ===")
        for f in findings:
            v = run_critic(f, report, acknowledged=set())
            print(f"  • {f.kind:<18} → {v.decision:<15} ({v.reason})")

    _line()
    print("① 첫 접촉 (사용자가 아직 아무 설명 안 함)\n")
    with session_scope() as s:
        report = analyze(s, uid, clock.today())
        res = decide(s, uid, report, acknowledged=set(), now=now)
        print(f"먼저 말 걸기? {res.should_speak}  |  이유: {res.reason}")
        if res.should_speak:
            print(f"결정: {res.primary.decision}  (trigger={res.primary.finding.kind})")
            print(f"미룬 신호: {res.suppressed}")
            print("\n💬 MoneyMate:")
            print("   " + res.fallback_message.replace("\n", "\n   "))
            record_event(s, uid, res, now=now)  # 말했으니 기록 → 알림 피로 방지 근거

    _line()
    print("② 2시간 뒤 다시 판단 (알림 피로 방지 확인)\n")
    with session_scope() as s:
        report = analyze(s, uid, clock.today())
        res = decide(s, uid, report, acknowledged=set(), now=now + timedelta(hours=2))
        print(f"먼저 말 걸기? {res.should_speak}  |  이유: {res.reason}")

    _line()
    user_reply = "아 이번주 시험기간이라 계속 배달시켜먹었어ㅠㅠ"
    tokens = infer_ack_tokens(user_reply)
    print(f'③ 사용자 답변: "{user_reply}"')
    print(f"   → 추출된 맥락 토큰: {tokens}\n")
    with session_scope() as s:
        report = analyze(s, uid, clock.today())
        # 시험기간은 배달 급증을 설명 → delivery/weekly 는 빠지고, 카드/예산 코칭이 남음
        res = decide(s, uid, report, acknowledged=tokens, now=now)
        print(f"먼저 말 걸기? {res.should_speak}  |  이유: {res.reason}")
        if res.should_speak:
            print(f"결정: {res.primary.decision}  (trigger={res.primary.finding.kind})")
            print("\n💬 MoneyMate:")
            print("   " + res.fallback_message.replace("\n", "\n   "))

    print("\n✅ STEP 9 완료: Analyst → Critic → Proactive (알림 피로 방지 포함) OK")


if __name__ == "__main__":
    run()
