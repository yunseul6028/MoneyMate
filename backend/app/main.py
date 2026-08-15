"""MoneyMate FastAPI 앱 (STEP 11 프리뷰).

한 페이지 UI(app/web/index.html) + 최소 API 를 서빙한다.
  GET  /                 대시보드 + 채팅 UI
  GET  /api/dashboard    금융 건강 상태 데이터
  GET  /api/proactive    AI 가 먼저 건네는 메시지
  POST /api/chat         사용자 질문 → 코치 답변
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.agents.coach import speak
from app.agents.critic import infer_ack_tokens
from app.agents.proactive import decide
from app.core import categories as C
from app.core import clock
from app.db.database import init_db, session_scope
from app.db.models import Transaction, User, UserProfile
from app.llm.factory import get_llm
from app.providers.mock_provider import MockFinancialDataProvider
from app.services.analysis import analyze
from app.services.chat import chat_answer
from app.services.classifier import record_correction
from app.services import transfers as transfers_svc
from app.services.dashboard import build_dashboard
from app.services.ingest import ingest_transactions
from app.services.simulation import (
    is_purchase_question,
    parse_amount,
    simulate_and_explain,
)

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
    return clock.now()


class ChatIn(BaseModel):
    message: str


class IngestIn(BaseModel):
    text: str
    payment_method: str = "credit"


class CorrectIn(BaseModel):
    category: str


class SimulateIn(BaseModel):
    amount: int
    on_credit: bool = True
    note: str = ""


class ProfileIn(BaseModel):
    name: str | None = None
    monthly_budget: int | None = None


class ResolveIn(BaseModel):
    person: str
    kind: str  # friend | other
    category: str = "식음료"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/dashboard")
def dashboard() -> dict:
    with session_scope() as s:
        uid = _demo_user_id(s)
        user = s.get(User, uid)
        report = analyze(s, uid, clock.today())
        return build_dashboard(report, user.name)


@app.get("/api/proactive")
def proactive() -> dict:
    """AI 가 지금 먼저 말을 걸지 판단해 메시지를 반환(기록은 하지 않음 — 프리뷰)."""
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        report = analyze(s, uid, clock.today())
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


@app.get("/api/profile")
def get_profile() -> dict:
    with session_scope() as s:
        uid = _demo_user_id(s)
        u = s.get(User, uid)
        p = s.query(UserProfile).filter(UserProfile.user_id == uid).first()
        return {
            "name": u.name,
            "monthly_budget": p.monthly_budget if p else 0,
            "card_billing_day": p.card_billing_day if p else 14,
        }


@app.patch("/api/profile")
def update_profile(inp: ProfileIn) -> dict:
    """온보딩/설정에서 이름·월 예산 저장."""
    with session_scope() as s:
        uid = _demo_user_id(s)
        u = s.get(User, uid)
        p = s.query(UserProfile).filter(UserProfile.user_id == uid).first()
        if inp.name and inp.name.strip():
            u.name = inp.name.strip()[:80]
        if inp.monthly_budget and inp.monthly_budget > 0:
            p.monthly_budget = inp.monthly_budget
        return {"ok": True, "name": u.name, "monthly_budget": p.monthly_budget}


@app.get("/api/transfers")
def transfers() -> dict:
    """사람 송금 요약 + 미해결(처음 본 사람) 목록 + 정산 요약."""
    with session_scope() as s:
        uid = _demo_user_id(s)
        summ = transfers_svc.summarize(s, uid)
        summ["settlement"] = analyze(s, uid, clock.today()).settlement
        summ["queue"] = transfers_svc.unresolved_tx_queue(s, uid)
        return summ


@app.post("/api/persons/resolve")
def resolve_person(inp: ResolveIn) -> dict:
    """사람 분류 저장(친구 N빵→식음료 / 아니면 지정 카테고리). 이후 자동 반영."""
    if inp.category not in C.EXPENSE_CATEGORIES:
        return {"ok": False, "error": "unknown_category"}
    with session_scope() as s:
        uid = _demo_user_id(s)
        rule = transfers_svc.resolve(s, uid, inp.person, inp.kind, inp.category)
        return {"ok": True, "person": rule.person_key,
                "kind": rule.kind, "category": rule.category}


@app.post("/api/ingest")
def ingest(inp: IngestIn) -> dict:
    """카드 결제 내역 텍스트를 받아 각 줄을 자동 분류·저장."""
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        items = ingest_transactions(
            s, uid, inp.text, inp.payment_method, clock.today(), llm
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


@app.post("/api/simulate")
def simulate(inp: SimulateIn) -> dict:
    """가상 소비 시뮬레이션 — 실제 결제 없이 재무 영향 계산 + 코치 설명."""
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        report = analyze(s, uid, clock.today())
        res = simulate_and_explain(
            llm, report, inp.amount, inp.note or f"{inp.amount}원 지출", inp.on_credit
        )
    return {"kind": "simulation", **res}


@app.post("/api/chat")
def chat(inp: ChatIn) -> dict:
    llm = get_llm()
    with session_scope() as s:
        uid = _demo_user_id(s)
        report = analyze(s, uid, clock.today())

        # 구매 질문 + 금액이 있으면 → 가상 소비 시뮬레이션
        if is_purchase_question(inp.message):
            amount = parse_amount(inp.message)
            if amount:
                res = simulate_and_explain(llm, report, amount, inp.message)
                return {"reply": res["reply"], "kind": "simulation",
                        "simulation": res["simulation"]}

        # 사용자가 맥락을 설명하면(예: "시험기간이라") → 코치 파이프라인으로 응답
        tokens = infer_ack_tokens(inp.message)
        if tokens:
            res = decide(s, uid, report, acknowledged=tokens, now=_now())
            if res.should_speak:
                return {"reply": speak(llm, res, report),
                        "kind": "coach", "decision": res.primary.decision}

        # 그 외 일반 질문 → 데이터 기반 답변
        return {"reply": chat_answer(llm, report, inp.message), "kind": "chat"}
