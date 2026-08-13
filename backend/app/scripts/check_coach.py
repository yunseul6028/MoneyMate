"""LLM Coach 검증 (STEP 10).  python -m app.scripts.check_coach

STEP 9 의 데모 흐름을 그대로 태우되, 마지막 출력 문장을 LLM Coach 가 생성한다.
키가 없으면 규칙기반 fallback 문구가 나온다(그래도 흐름은 동일).
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.agents.coach import speak
from app.agents.critic import infer_ack_tokens
from app.agents.proactive import decide, record_event
from app.config import settings
from app.db.database import init_db, session_scope
from app.llm.factory import get_llm
from app.providers.mock_provider import MockFinancialDataProvider
from app.services.analysis import analyze


def run() -> None:
    init_db()
    llm = get_llm()
    print(f"[LLM] provider={llm.name} available={llm.available}\n")

    provider = MockFinancialDataProvider()
    with session_scope() as s:
        provider.ensure_global_rules(s)
        user = provider.ensure_demo_user(s)
        provider.sync_transactions(s, user.id)
        uid = user.id

    now = datetime(2026, 8, 13, 21, 0, tzinfo=timezone.utc)

    print("─" * 64)
    print("① 먼저 말 걸기 (배달 급증 감지)\n")
    with session_scope() as s:
        report = analyze(s, uid, settings.demo_today)
        res = decide(s, uid, report, acknowledged=set(), now=now)
        print("💬 MoneyMate:")
        print("   " + speak(llm, res, report).replace("\n", "\n   "))
        record_event(s, uid, res, now=now)

    print("\n" + "─" * 64)
    reply = "아 이번주 시험기간이라 계속 배달시켜먹었어ㅠㅠ"
    print(f'② 사용자: "{reply}"\n')
    with session_scope() as s:
        report = analyze(s, uid, settings.demo_today)
        res = decide(s, uid, report, acknowledged=infer_ack_tokens(reply), now=now)
        print("💬 MoneyMate:")
        print("   " + speak(llm, res, report).replace("\n", "\n   "))

    print("\n✅ STEP 10 완료: LLM Coach 연결 OK")


if __name__ == "__main__":
    run()
