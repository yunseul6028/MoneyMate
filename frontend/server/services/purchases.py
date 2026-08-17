"""애매한 카드결제('기타') → 사용자에게 질문 + 개인화 학습 (STEP: 기타 분류 질문).

규칙/AI 로도 카테고리를 못 정해 '기타'로 떨어진 지출을, 정산 흐름처럼
챗에서 가맹점 단위로 하나씩 물어본다. 답하면:
  - record_correction 으로 개인화 규칙 저장(다음부터 같은 가맹점 자동 분류)
  - 같은 가맹점의 기존 '기타' 지출도 전부 그 카테고리로 갱신

사람 간 송금(마스킹된 이름)은 transfers 흐름이 담당하므로 여기선 제외한다.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from server.core import categories as C
from server.db.models import Transaction
from server.services.classifier import normalize, record_correction
from server.services.transfers import is_person


def _eta_expenses(session: Session, user_id: int) -> list[Transaction]:
    """'기타'로 분류된 지출들 (사람 송금 제외)."""
    txs = (
        session.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.tx_type == C.EXPENSE,
            Transaction.category == C.ETC,
        )
        .all()
    )
    return [t for t in txs if not is_person(t.merchant)]


def unresolved_purchase_queue(session: Session, user_id: int) -> list[dict]:
    """물어볼 '기타' 지출을 가맹점 단위로 묶어 하나씩(최신 대표건 기준, 최신순).

    사용자가 이미 확정한(category_source='user') 건은 다시 묻지 않는다.
    """
    groups: dict[str, dict] = {}
    for t in _eta_expenses(session, user_id):
        if t.category_source == "user":  # 이미 사용자가 '기타'로 확정 → 재질문 안 함
            continue
        key = normalize(t.merchant)
        g = groups.get(key)
        if g is None:
            g = {"merchant": t.merchant, "id": t.id, "amount": round(t.amount),
                 "date": t.tx_date.isoformat(), "count": 0, "total": 0.0,
                 "_d": t.tx_date}
            groups[key] = g
        g["count"] += 1
        g["total"] += t.amount
        if t.tx_date > g["_d"]:  # 대표건 = 가장 최근 거래
            g.update(merchant=t.merchant, id=t.id, amount=round(t.amount),
                     date=t.tx_date.isoformat(), _d=t.tx_date)

    out = []
    for g in groups.values():
        g["total"] = round(g["total"])
        g.pop("_d", None)
        out.append(g)
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def categorize_purchase(session: Session, user_id: int, merchant: str, category: str) -> int:
    """'기타' 지출을 사용자가 고른 카테고리로 확정.

    개인화 규칙 저장 + 같은 가맹점의 기존 '기타' 지출 전부 갱신. 갱신 건수 반환.
    """
    if category not in C.EXPENSE_CATEGORIES:
        raise ValueError(f"unknown_category: {category}")
    key = normalize(merchant)
    record_correction(session, user_id, merchant, category)  # 개인화 학습
    updated = 0
    for t in _eta_expenses(session, user_id):
        if normalize(t.merchant) == key:
            t.category = category
            t.category_source = "user"
            updated += 1
    session.flush()
    return updated
