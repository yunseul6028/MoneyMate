"""Vercel Python 서버리스 진입점 (Next.js 프로젝트에 통합).

/api/* 요청은 next.config 의 rewrite 로 이 함수에 오고, FastAPI 가 내부 라우팅한다.
로컬 개발은 `uvicorn server.main:app --port 8000` 로 따로 띄운다(next.config 가 그쪽으로 프록시).
"""
from server.main import app  # noqa: F401  (ASGI FastAPI 앱)
