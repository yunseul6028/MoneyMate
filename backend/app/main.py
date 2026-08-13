"""MoneyMate FastAPI 앱 (STEP 11 프리뷰).

한 페이지 UI(app/web/index.html) + 최소 API 를 서빙한다.
  GET  /                 대시보드 + 채팅 UI
  GET  /api/dashboard    금융 건강 상태 데이터
  GET  /api/proactive    AI 가 먼저 건네는 메시지
  POST /api/chat         사용자 질문 → 코치 답변
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agents.coach import speak
from app.agents.critic import infer_ack_tokens
from app.agents.proactive import decide
from app.config import settings
from app.core import categories as C
from app.db.database import init_db, session_scope
from app.db.models import Transaction, User
from app.llm.factory import get_llm
from app.providers.mock_provider import MockFinancialDataProvider
from app.services.analysis import analyze
from app.services.chat import chat_answer
from app.services.classifier import record_correction
from app.services.dashboard import build_dashboard
from app.services.ingest import ingest_transactions

WEB_DIR = Path(__file__).resolve().parent / "web"


def _seed() -> None:
    init_db()
    provider = MockFinancialDataProvider()
    with session_scope() as s:
        provider.ensure_global_rules(s)
        user = provider.ensure_demo_user(s)
        provider.sync_transactions(s, user.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed()
    yield


app = FastAPI(title="MoneyMate", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _demo_user_id(s) -> int:
    return s.query(User).order_by(User.id.asc()).first().id


def _now() -> datetime:
    # 데모 기준 '오늘' 정오
    d = settings.demo_today
    return datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)


class ChatIn(BaseModel):
    message: str


class IngestIn(BaseModel):
    text: str
    payment_method: str = "credit"


class CorrectIn(BaseModel):
    category: str


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/dashboard")
def dashboard() -> dict:
    with session_scope() as s:
        uid = _demo_user_id(s)
        user = s.get(User, uid)
        report = analyze(s, uid, settings.demo_today)
        return build_dashboard(report, user.name)


@app.get("/api/proactive")
def proactive() -> dict:
    """AI 가 지금 먼저 말을 걸지 판단해 메시지를 반환(기록은 하지 않음 — 프리뷰)."""
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        report = analyze(s, uid, settings.demo_today)
        res = decide(s, uid, report, acknowledged=set(), now=_now())
        if not res.should_speak:
            return {"should_speak": False, "message": "", "decision": None}
        return {
            "should_speak": True,
            "decision": res.primary.decision,
            "trigger": res.primary.finding.kind,
            "message": speak(llm, res, report),
        }


@app.get("/api/categories")
def categories() -> dict:
    return {"expense": C.EXPENSE_CATEGORIES}


@app.post("/api/ingest")
def ingest(inp: IngestIn) -> dict:
    """카드 결제 내역 텍스트를 받아 각 줄을 자동 분류·저장."""
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        items = ingest_transactions(
            s, uid, inp.text, inp.payment_method, settings.demo_today, llm
        )
    return {"added": len(items), "items": items}


@app.post("/api/transactions/{tx_id}/category")
def correct_category(tx_id: int, inp: CorrectIn) -> dict:
    """분류 수정 → 개인화 규칙으로 학습(다음부터 같은 가맹점 자동 반영)."""
    if inp.category not in C.EXPENSE_CATEGORIES:
        return {"ok": False, "error": "unknown_category"}
    with session_scope() as s:
        tx = s.get(Transaction, tx_id)
        if tx is None:
            return {"ok": False, "error": "not_found"}
        tx.category = inp.category
        tx.category_source = "user"
        record_correction(s, tx.user_id, tx.merchant, inp.category)
    return {"ok": True, "category": inp.category, "source": "user"}


@app.post("/api/chat")
def chat(inp: ChatIn) -> dict:
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        report = analyze(s, uid, settings.demo_today)

        # 사용자가 맥락을 설명하면(예: "시험기간이라") → 코치 파이프라인으로 응답
        tokens = infer_ack_tokens(inp.message)
        if tokens:
            res = decide(s, uid, report, acknowledged=tokens, now=_now())
            if res.should_speak:
                return {"reply": speak(llm, res, report),
                        "kind": "coach", "decision": res.primary.decision}

        # 그 외 일반 질문 → 데이터 기반 답변
        return {"reply": chat_answer(llm, report, inp.message), "kind": "chat"}
