"""송금 상대(사람) 분류 + 정산 (STEP: 친구 송금).

흐름
  - 사람 송금(masked 이름, tx_type=transfer)에서 처음 본 사람 → 사용자에게 물어봄.
  - '친구 정산' → PersonRule(kind=friend, category=식음료) 저장 → 이후 자동 식음료.
  - '친구 아님' → 사용자가 고른 카테고리로 저장.
  - 정산 netting: 같은 카테고리에서 (보낸 돈) − (받은 돈) 만 내 지출로 남김
    → "내가 다 긁고 친구가 입금하면 내 몫만 지출".
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from server.db.models import PersonRule, Transaction


def person_key(merchant: str) -> str:
    """'토스 정*영', '정*영' → '정*영' (송금 서비스 접두어 제거)."""
    s = merchant.strip()
    for pre in ("토스 ", "토스퀵 ", "카카오페이 "):
        if s.startswith(pre):
            s = s[len(pre):]
    s = re.sub(r"[()（）_].*$", "", s).strip()  # 괄호 이후 꼬리 제거
    return s


def is_person(merchant: str) -> bool:
    """마스킹된 사람 이름인가 (가운데 * 포함)."""
    return "*" in (merchant or "")


def get_rules(session: Session, user_id: int) -> dict[str, PersonRule]:
    rows = session.query(PersonRule).filter(PersonRule.user_id == user_id).all()
    return {r.person_key: r for r in rows}


def person_transfers(session: Session, user_id: int) -> list[Transaction]:
    txs = (
        session.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.tx_type == "transfer")
        .all()
    )
    return [t for t in txs if is_person(t.merchant)]


def summarize(session: Session, user_id: int) -> dict:
    """사람별 송금 요약 + 미해결(처음 본 사람) 목록."""
    rules = get_rules(session, user_id)
    agg: dict[str, dict] = {}
    for t in person_transfers(session, user_id):
        k = person_key(t.merchant)
        a = agg.setdefault(k, {"person": k, "sent": 0.0, "received": 0.0, "count": 0})
        if t.direction == "out":
            a["sent"] += t.amount
        else:
            a["received"] += t.amount
        a["count"] += 1

    people, unresolved = [], []
    for k, a in sorted(agg.items(), key=lambda x: -(x[1]["sent"] + x[1]["received"])):
        rule = rules.get(k)
        a["net"] = round(a["sent"] - a["received"])
        a["sent"] = round(a["sent"])
        a["received"] = round(a["received"])
        if rule:
            a["kind"] = rule.kind
            a["category"] = rule.category
            people.append(a)
        else:
            unresolved.append(a)
    return {"resolved": people, "unresolved": unresolved}


def unresolved_tx_queue(session: Session, user_id: int) -> list[dict]:
    """미해결 사람 송금을 '개별 거래' 단위로 (최신순). 묶지 않고 하나씩 물어보기용."""
    rules = get_rules(session, user_id)
    out = []
    for t in person_transfers(session, user_id):
        k = person_key(t.merchant)
        if k in rules:
            continue
        out.append({
            "id": t.id,
            "person": k,
            "date": t.tx_date.isoformat(),
            "amount": round(t.amount),
            "direction": t.direction,
        })
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def resolve(session: Session, user_id: int, person: str, kind: str, category: str) -> PersonRule:
    """사람 분류 저장(개인화). friend 는 기본 식음료."""
    key = person_key(person)
    if kind == "friend" and not category:
        category = "식음료"
    rule = (
        session.query(PersonRule)
        .filter(PersonRule.user_id == user_id, PersonRule.person_key == key)
        .first()
    )
    if rule:
        rule.kind, rule.category = kind, category
    else:
        rule = PersonRule(user_id=user_id, person_key=key, kind=kind, category=category)
        session.add(rule)
    session.flush()
    return rule


# 정산 인정 시간창: 받은 정산은 '송금 ±N일 내에 그만한 내 지출'이 있어야 차감 인정
SETTLEMENT_WINDOW_DAYS = 3


def _has_nearby_expense(expenses: list[Transaction], when, min_amount: float) -> bool:
    """송금 시점 ±N일 내에 min_amount 이상인 내 지출이 있는지 (정산 근거)."""
    for e in expenses:
        if e.amount >= min_amount and abs((e.tx_date - when).days) <= SETTLEMENT_WINDOW_DAYS:
            return True
    return False


def settlement_netting(session: Session, user_id: int, start, end) -> dict[str, float]:
    """해결된 사람 송금을 카테고리별 순지출로 환산 (실제 정산만).

    - 보낸 정산(out): 내가 낸 몫 → 그대로 내 지출(+). (친구가 긁은 경우 내 카드엔 지출 없음)
    - 받은 정산(in): 내가 ±SETTLEMENT_WINDOW_DAYS 일 내에 그만한 금액을 쓴 지출이 있을 때만
      정산으로 인정해 차감(−). 무관한/한참 지난 입금은 정산으로 치지 않는다.
    분석 엔진이 이 결과를 카테고리 소비에 더한다(음수는 차감).
    """
    rules = get_rules(session, user_id)
    expenses = (
        session.query(Transaction)
        .filter(Transaction.user_id == user_id, Transaction.tx_type == "expense")
        .all()
    )
    net: dict[str, float] = {}
    for t in person_transfers(session, user_id):
        if not (start <= t.tx_date <= end):
            continue
        rule = rules.get(person_key(t.merchant))
        if not rule:
            continue
        if t.direction == "out":
            net[rule.category] = net.get(rule.category, 0.0) + t.amount
        elif _has_nearby_expense(expenses, t.tx_date, t.amount):
            net[rule.category] = net.get(rule.category, 0.0) - t.amount
        # else: 근처에 그만한 지출 없음 → 정산 아님(차감하지 않음)
    return net
