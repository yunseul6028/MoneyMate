"""Vercel Python(서버리스) 진입점.

Vercel 은 이 파일의 ASGI `app` 을 서빙한다. 모든 요청은 vercel.json 라우팅으로 여기로 온다.
로컬 개발은 여전히 `uvicorn app.main:app` 를 쓰면 된다.
"""
from app.main import app  # noqa: F401  (ASGI FastAPI 앱)
