"""LLM 연결 테스트 (STEP 10).  python -m app.scripts.check_llm

Gemini 키가 .env 에 들어갔는지, 실제로 응답이 오는지 확인한다.
"""
from __future__ import annotations

from app.config import settings
from app.llm.factory import get_llm


def run() -> None:
    print(f"LLM_PROVIDER = {settings.llm_provider}")
    llm = get_llm()
    print(f"provider = {llm.name}  |  available = {llm.available}")
    if hasattr(llm, "model"):
        print(f"model = {llm.model}")

    if not llm.available:
        print("\n⚠ LLM 키가 없어 mock 상태야. backend/.env 의 GEMINI_API_KEY 를 채우면 활성화돼.")
        print("   (지금도 앱은 규칙기반으로 정상 동작해.)")
        return

    print("\n연결 테스트 중...")
    try:
        out = llm.chat(
            system="너는 친근한 한국어 대학생 금융 친구야.",
            user="한 문장으로 반갑게 인사해줘.",
            max_tokens=60,
        )
        print(f"✅ 응답: {out}")
        print("\n✅ LLM 연결 OK — 이제 Coach 가 진짜 문장을 생성할 수 있어.")
    except Exception as e:
        print(f"❌ 호출 실패: {type(e).__name__}: {e}")
        print("   키/모델명/네트워크를 확인해줘. (모델명 예: gemini-2.5-flash, gemini-2.0-flash)")


if __name__ == "__main__":
    run()
