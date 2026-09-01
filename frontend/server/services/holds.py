"""고민함 — 충동구매 유예(cooling-off).

'사도 될까?' 순간 바로 안 사고 재워두면(add_hold), 실제 경과 시간이 지난 뒤
에이전트가 다시 물어본다. 접으면(dropped) '아낀 돈'에 누적된다.
쿨다운은 real wall-clock(datetime.now) 기준 — 데모 시계와 무관.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from server.db.models import PurchaseHold


def add_hold(session: Session, user_id: int, item: str, amount: float, hours: float = 24) -> PurchaseHold:
    now = datetime.now()
    h = PurchaseHold(
        user_id=user_id,
        item=(item or "이 지출")[:120],
        amount=float(amount),
        status="pending",
        created_at=now,
        remind_at=now + timedelta(hours=hours),
    )
    session.add(h)
    session.flush()
    return h


def _fmt_elapsed(created: datetime, now: datetime) -> str:
    sec = max(0, (now - created).total_seconds())
    if sec < 3600:
        return f"{max(1, int(sec // 60))}분째"
    if sec < 86400:
        return f"{int(sec // 3600)}시간째"
    return f"{int(sec // 86400)}일째"


def _fmt_remaining(remind: datetime, now: datetime) -> str:
    sec = (remind - now).total_seconds()
    if sec <= 0:
        return "결정할 시간"
    if sec < 3600:
        return f"{max(1, int(sec // 60))}분 뒤"
    if sec < 86400:
        return f"{int(sec // 3600)}시간 뒤"
    return f"{int(sec // 86400)}일 뒤"


def list_holds(session: Session, user_id: int) -> dict:
    now = datetime.now()
    pending = (
        session.query(PurchaseHold)
        .filter(PurchaseHold.user_id == user_id, PurchaseHold.status == "pending")
        .order_by(PurchaseHold.created_at.asc())
        .all()
    )
    items = [
        {
            "id": h.id,
            "item": h.item,
            "amount": round(h.amount),
            "elapsed": _fmt_elapsed(h.created_at, now),
            "remaining": _fmt_remaining(h.remind_at, now),
            "due": now >= h.remind_at,
        }
        for h in pending
    ]
    dropped = (
        session.query(PurchaseHold)
        .filter(PurchaseHold.user_id == user_id, PurchaseHold.status == "dropped")
        .all()
    )
    return {
        "items": items,
        "count": len(items),
        "saved_total": round(sum(h.amount for h in dropped)),
        "saved_count": len(dropped),
    }


def decide_hold(session: Session, user_id: int, hold_id: int, decision: str) -> PurchaseHold | None:
    if decision not in ("bought", "dropped"):
        return None
    h = session.get(PurchaseHold, hold_id)
    if h is None or h.user_id != user_id:
        return None
    h.status = decision
    h.decided_at = datetime.now()
    session.flush()
    return h
