"""카드 결제 내역 입력 → 자동 분류 → 저장 (STEP 7 실사용 연결).

"스타벅스 5500" 같은 줄들을 파싱해서 분류기(classify)에 태운다.
처음 보는 가맹점은 LLM(Gemini) 폴백으로 분류 — classifier 의 llm 훅을 실제로 연결.
"""
from __future__ import annotations

import re
from datetime import date

from sqlalchemy.orm import Session

from server.core import categories as C
from server.db.models import Transaction
from server.llm.base import LLMProvider
from server.services.classifier import classify

# 줄 끝의 금액(콤마/원 허용)만 추출. 앞부분 전체를 가맹점명으로.
_AMOUNT_RE = re.compile(r"([\d][\d,]*)\s*원?\s*$")


def parse_lines(text: str) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = _AMOUNT_RE.search(line)
        if not m:
            continue
        amount = int(m.group(1).replace(",", ""))
        merchant = line[: m.start()].strip(" -\t·|,")
        if merchant and amount > 0:
            items.append((merchant, amount))
    return items


def make_llm_classifier(llm: LLMProvider):
    """가맹점명 → 카테고리 하나를 고르는 LLM 분류기. 없으면 None(폴백 skip)."""
    if not llm.available:
        return None
    cats = ", ".join(C.EXPENSE_CATEGORIES)
    system = (
        "너는 가맹점명을 정해진 카테고리 중 하나로 분류하는 분류기야. "
        "설명 없이 카테고리 이름 하나만 정확히 답해."
    )

    def _classify(merchant: str) -> str | None:
        try:
            out = llm.chat(
                system,
                f"가맹점: {merchant}\n선택지: {cats}\n카테고리:",
                temperature=0.0,
                max_tokens=20,
            ).strip()
        except Exception:
            return None
        if out in C.EXPENSE_CATEGORIES:
            return out
        for c in C.EXPENSE_CATEGORIES:  # 부분 포함 허용
            if c in out:
                return c
        return None

    return _classify


_SOURCE_LABEL = {"user": "내 설정", "rule": "규칙", "llm": "AI 분류", "fallback": "기타"}


def ingest_transactions(
    session: Session,
    user_id: int,
    text: str,
    payment_method: str,
    when: date,
    llm: LLMProvider,
) -> list[dict]:
    parsed = parse_lines(text)
    llm_clf = make_llm_classifier(llm)
    results: list[dict] = []
    for merchant, amount in parsed:
        c = classify(session, user_id, merchant, llm=llm_clf)
        tx = Transaction(
            user_id=user_id,
            tx_date=when,
            merchant=merchant,
            amount=amount,
            category=c.category,
            tx_type=C.EXPENSE,
            payment_method=payment_method,
            category_source=c.source,
        )
        session.add(tx)
        session.flush()
        results.append({
            "id": tx.id,
            "merchant": merchant,
            "amount": amount,
            "category": c.category,
            "source": c.source,
            "source_label": _SOURCE_LABEL.get(c.source, c.source),
        })
    return results
