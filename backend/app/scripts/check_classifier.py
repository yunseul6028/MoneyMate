"""분류기 검증 (STEP 7).  python -m app.scripts.check_classifier"""
from __future__ import annotations

from app.db.database import init_db, session_scope
from app.providers.mock_provider import MockFinancialDataProvider
from app.services.classifier import classify, record_correction


def run() -> None:
    init_db()
    provider = MockFinancialDataProvider()
    with session_scope() as s:
        provider.ensure_global_rules(s)
        user = provider.ensure_demo_user(s)
        provider.sync_transactions(s, user.id)
        uid = user.id

    samples = [
        "CU 강남점", "스타벅스 강남R점", "올리브영 신촌점",
        "쿠팡", "교통카드 충전", "넷플릭스", "배달의민족",
        "동네초밥 무한리필",  # 처음 보는 가맹점 → LLM 없으면 기타
    ]

    print("=== 규칙 기반 분류 ===")
    with session_scope() as s:
        for m in samples:
            r = classify(s, uid, m)
            print(f"  {m:<18} → {r.category:<7} [{r.source}]")

    print("\n=== 사용자 수정 학습(개인화) ===")
    with session_scope() as s:
        before = classify(s, uid, "동네초밥 무한리필")
        print(f"  수정 전: 동네초밥 무한리필 → {before.category} [{before.source}]")
        record_correction(s, uid, "동네초밥 무한리필", "식음료")
    with session_scope() as s:
        after = classify(s, uid, "동네초밥 무한리필점")  # 지점명 달라도 매칭
        print(f"  수정 후: 동네초밥 무한리필점 → {after.category} [{after.source}]")

    assert after.source == "user" and after.category == "식음료", "개인화 학습 실패"
    print("\n✅ STEP 7 완료: 규칙 분류 + 개인화 학습 OK")


if __name__ == "__main__":
    run()
