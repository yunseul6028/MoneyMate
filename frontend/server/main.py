"""MoneyMate FastAPI 앱 (API 서버).

UI 는 Next.js 앱(frontend/, 기본 :3000)이 담당하고, 여기선 API 만 서빙한다.
  GET  /api/dashboard    금융 건강 상태 데이터
  GET  /api/proactive    AI 가 먼저 건네는 메시지
  POST /api/chat         사용자 질문 → 코치 답변
  ...  /api/transfers · /api/simulate · /api/ingest · /api/dev/* 등
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.agents.coach import speak
from server.agents.critic import infer_ack_tokens
from server.agents.proactive import decide
from server.core import categories as C
from server.core import clock
from server.db.database import init_db, session_scope
from server.db.models import AgentEvent, PersonRule, Transaction, User, UserProfile
from server.llm.factory import get_llm
from server.providers.mock_provider import MockFinancialDataProvider
from server.services.analysis import analyze
from server.services.chat import chat_answer
from server.services.classifier import record_correction
from server.services import transfers as transfers_svc
from server.services.dashboard import build_dashboard
from server.services.ingest import ingest_transactions
from server.services import purchases as purchases_svc
from server.services.simulation import (
    is_purchase_question,
    parse_amount,
    simulate_and_explain,
)

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

# 서버리스(Vercel)에서는 lifespan 이 안 돌 수 있어, 첫 요청 때 시드를 보장한다(멱등).
_seeded = False


@app.middleware("http")
async def _seed_guard(request, call_next):
    global _seeded
    if not _seeded:
        try:
            _seed()
        except Exception:
            pass
        _seeded = True
    return await call_next(request)


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


class PurchaseCatIn(BaseModel):
    merchant: str
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


class DevEventIn(BaseModel):
    kind: str


# 목업 테스트용 프리셋: (가맹점, 금액, 카테고리, tx_type, 결제수단, 방향, 메모)
_DEV_PRESETS: dict[str, tuple] = {
    "cafe": ("메가커피", 4_500, "카페", "expense", "check", "out", None),
    "delivery": ("배달의민족", 21_000, "식음료", "expense", "credit", "out", "배달"),
    "shopping": ("무신사", 120_000, "쇼핑", "expense", "credit", "out", None),
    "friend_in": ("테*트", 30_000, "기타", "transfer", "transfer", "in", "받음"),
}


@app.post("/api/dev/event")
def dev_event(inp: DevEventIn) -> dict:
    """테스트용 이벤트 발생 — mock 거래를 즉석 주입해서 앱 반응 확인."""
    from datetime import timedelta

    today = clock.today()
    with session_scope() as s:
        uid = _demo_user_id(s)

        def add(m, a, c, tt, pm, d, memo, when=today):
            s.add(Transaction(
                user_id=uid, tx_date=when, merchant=m, amount=a, category=c,
                tx_type=tt, payment_method=pm, direction=d,
                category_source="seed", memo=memo,
            ))

        if inp.kind == "delivery_spike":
            for i in range(5):  # 최근 5일 배달 폭증 → proactive 트리거
                add("배달의민족", 20_000 + i * 1_000, "식음료", "expense",
                    "credit", "out", "배달", today - timedelta(days=i))
        elif inp.kind in _DEV_PRESETS:
            add(*_DEV_PRESETS[inp.kind])
        else:
            return {"ok": False, "error": "unknown_kind"}
        s.flush()
    return {"ok": True, "kind": inp.kind}


@app.post("/api/dev/reset")
def dev_reset() -> dict:
    """데모 데이터로 초기화 (거래·사람규칙·에이전트기록 삭제 후 재시드)."""
    with session_scope() as s:
        uid = _demo_user_id(s)
        s.query(Transaction).filter_by(user_id=uid).delete()
        s.query(PersonRule).filter_by(user_id=uid).delete()
        s.query(AgentEvent).filter_by(user_id=uid).delete()
        s.flush()
        MockFinancialDataProvider().sync_transactions(s, uid)
    return {"ok": True}


@app.get("/")
def root() -> dict:
    """MoneyMate API. UI 는 Next.js 앱(기본 http://localhost:3000)에서 제공."""
    return {"app": "MoneyMate API", "ui": "http://localhost:3000", "docs": "/docs"}


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
    """사람 분류 저장(친구 정산→식음료 / 아니면 지정 카테고리). 이후 자동 반영."""
    if inp.category not in C.EXPENSE_CATEGORIES:
        return {"ok": False, "error": "unknown_category"}
    with session_scope() as s:
        uid = _demo_user_id(s)
        rule = transfers_svc.resolve(s, uid, inp.person, inp.kind, inp.category)
        return {"ok": True, "person": rule.person_key,
                "kind": rule.kind, "category": rule.category}


@app.post("/api/transfers/{tx_id}/categorize")
def categorize_transfer(tx_id: int, inp: CorrectIn) -> dict:
    """송금 건 하나만 일회성으로 분류(사람 규칙은 안 남김). 친구 정산만 기억한다."""
    if inp.category not in C.EXPENSE_CATEGORIES:
        return {"ok": False, "error": "unknown_category"}
    with session_scope() as s:
        tx = s.get(Transaction, tx_id)
        if tx is None:
            return {"ok": False, "error": "not_found"}
        tx.category = inp.category
        # 이 거래만 소비/소득으로 편입 (보냄→지출, 받음→소득). PersonRule 은 만들지 않음.
        tx.tx_type = "expense" if tx.direction == "out" else "income"
        tx.category_source = "user"
        return {"ok": True, "category": inp.category}


@app.get("/api/purchases/unresolved")
def unresolved_purchases() -> dict:
    """규칙/AI 로도 못 정해 '기타'로 남은 카드결제를 가맹점 단위로 (질문 대기열)."""
    with session_scope() as s:
        uid = _demo_user_id(s)
        return {"queue": purchases_svc.unresolved_purchase_queue(s, uid)}


@app.post("/api/purchases/categorize")
def categorize_purchase(inp: PurchaseCatIn) -> dict:
    """'기타' 카드결제를 사용자가 고른 카테고리로 확정 → 개인화 학습 + 같은 가맹점 전부 반영."""
    if inp.category not in C.EXPENSE_CATEGORIES:
        return {"ok": False, "error": "unknown_category"}
    with session_scope() as s:
        uid = _demo_user_id(s)
        n = purchases_svc.categorize_purchase(s, uid, inp.merchant, inp.category)
        return {"ok": True, "category": inp.category, "updated": n}


@app.post("/api/ingest")
def ingest(inp: IngestIn) -> dict:
    """카드 결제 내역 텍스트를 받아 각 줄을 자동 분류·저장.

    (프론트 수동 입력 UI 는 제거됨. 이 엔드포인트+분류기는 유지 —
     나중에 실제 카드/은행 API(RealFinancialDataProvider)나 파일 업로드를
     여기에 연결하면 됨. 자동 분류·개인화 파이프라인은 그대로 재사용.)"""
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
