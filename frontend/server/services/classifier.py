"""거래내역 자동 분류 (STEP 7).

분류 우선순위 (스펙 원칙: 명확하면 rule, 애매하면 LLM):
  1. 사용자 개인화 규칙 (merchant_rules.user_id = 해당 사용자, source='user')
  2. 전역 규칙        (merchant_rules.user_id = NULL)
  3. LLM 폴백         (STEP 10 에서 주입. 없으면 skip)
  4. 기타

사용자가 분류를 수정하면 record_correction 으로 개인화 규칙을 저장 → 다음부터 자동 반영.
LLM 은 '처음 보는/애매한 가맹점'에만 호출한다(비용·정확성).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from server.core import categories as C
from server.db.models import MerchantRule

# LLM 분류기 시그니처: (merchant) -> category | None
LLMClassifier = Callable[[str], str | None]


@dataclass
class Classification:
    category: str
    source: str  # user | rule | llm | fallback


def normalize(merchant: str) -> str:
    """가맹점명 정규화: 소문자 + 공백/기호 제거. 부분포함 매칭용."""
    s = merchant.lower().strip()
    for ch in (" ", "-", "_", ".", "(", ")", "점", "㈜", "주식회사"):
        s = s.replace(ch, "")
    return s


def _match_rules(rules: list[MerchantRule], norm_merchant: str) -> str | None:
    """정규화된 가맹점명에 rule 의 키가 포함되면 매칭. 긴 키 우선(더 구체적)."""
    best: tuple[int, str] | None = None
    for r in rules:
        key = normalize(r.merchant_key)
        if key and key in norm_merchant:
            if best is None or len(key) > best[0]:
                best = (len(key), r.category)
    return best[1] if best else None


def classify(
    session: Session,
    user_id: int,
    merchant: str,
    llm: LLMClassifier | None = None,
) -> Classification:
    norm = normalize(merchant)

    # 1) 개인화 규칙 우선
    user_rules = (
        session.query(MerchantRule)
        .filter(MerchantRule.user_id == user_id)
        .all()
    )
    hit = _match_rules(user_rules, norm)
    if hit:
        return Classification(hit, "user")

    # 2) 전역 규칙
    global_rules = (
        session.query(MerchantRule)
        .filter(MerchantRule.user_id.is_(None))
        .all()
    )
    hit = _match_rules(global_rules, norm)
    if hit:
        return Classification(hit, "rule")

    # 3) LLM 폴백 (주입된 경우에만)
    if llm is not None:
        guess = llm(merchant)
        if guess in C.EXPENSE_CATEGORIES:
            # 학습: LLM 결과를 전역 규칙으로 캐시해 다음부터 재사용
            _upsert_rule(session, merchant, guess, user_id=None, source="llm")
            return Classification(guess, "llm")

    # 4) 기타
    return Classification(C.ETC, "fallback")


def record_correction(
    session: Session, user_id: int, merchant: str, category: str
) -> None:
    """사용자가 분류를 수정 → 개인화 규칙으로 저장(원칙: 향후 동일 가맹점 개인화)."""
    if category not in C.EXPENSE_CATEGORIES:
        raise ValueError(f"알 수 없는 카테고리: {category}")
    _upsert_rule(session, merchant, category, user_id=user_id, source="user")


def _upsert_rule(
    session: Session, merchant: str, category: str, user_id: int | None, source: str
) -> None:
    key = normalize(merchant)
    existing = (
        session.query(MerchantRule)
        .filter(MerchantRule.merchant_key == key, MerchantRule.user_id.is_(user_id) if user_id is None
                else MerchantRule.user_id == user_id)
        .first()
    )
    if existing:
        existing.category = category
        existing.source = source
    else:
        session.add(MerchantRule(
            merchant_key=key, category=category, user_id=user_id, source=source
        ))
    session.flush()
