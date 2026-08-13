"""카테고리 정의 (단일 출처).

지출/소득 카테고리와 결제수단을 문자열 상수로 관리한다.
enum 대신 문자열을 쓰는 이유: LLM 분류 결과·DB 저장·JSON 직렬화가 모두 매끄럽고,
사용자가 새 카테고리를 정의할 여지를 남기기 위함.
"""
from __future__ import annotations

# --- 지출 카테고리 ---
FOOD = "식음료"
CAFE = "카페"
TRANSPORT = "교통"
SHOPPING = "쇼핑"
LIFE_BEAUTY = "생활/뷰티"
EDUCATION = "교육"
MEDICAL = "의료"
SUBSCRIPTION = "구독"
TRAVEL = "여행"
LEISURE = "여가"
ETC = "기타"

EXPENSE_CATEGORIES: list[str] = [
    FOOD, CAFE, TRANSPORT, SHOPPING, LIFE_BEAUTY,
    EDUCATION, MEDICAL, SUBSCRIPTION, TRAVEL, LEISURE, ETC,
]

# --- 소득 카테고리 ---
ALLOWANCE = "용돈"
PART_TIME = "알바"
SCHOLARSHIP = "장학금"
ETC_INCOME = "기타소득"

INCOME_CATEGORIES: list[str] = [ALLOWANCE, PART_TIME, SCHOLARSHIP, ETC_INCOME]

# --- 거래 방향 ---
EXPENSE = "expense"
INCOME = "income"

# --- 결제수단 ---
CREDIT = "credit"      # 신용카드 → 다음 카드 결제 예정액에 반영
CHECK = "check"        # 체크카드 (즉시 출금)
CASH = "cash"
TRANSFER = "transfer"  # 계좌이체

PAYMENT_METHODS: list[str] = [CREDIT, CHECK, CASH, TRANSFER]


def is_valid_expense_category(name: str) -> bool:
    return name in EXPENSE_CATEGORIES
