"""현실적인 대학생 Mock 원장 생성기 (STEP 6).

'오늘'을 기준으로 약 10주치 거래를 생성한다. 아래 7가지 시나리오를 데이터에 심는다.
  1. 정상적인 소비 (baseline: 식사/카페/교통)
  2. 시험기간 배달 증가   → 최근 1주(오늘 포함) 배달 급증
  3. 여행 일시적 지출 증가 → 지난달 중순 KTX+숙소 lump
  4. 쇼핑 과소비          → 지난달 말 무신사/쿠팡 대형결제
  5. 카드 사용 급증        → 최근으로 올수록 신용카드 결제 비중 증가
  6. 구독 서비스 증가      → 넷플릭스→+스포티파이→+ChatGPT/쿠팡와우 점증
  7. 소득 감소            → 이번 달 용돈/알바비 축소

중요: 숫자 계산은 상위 분석 엔진이 담당한다. 여기서는 '현실적인 원천 데이터'만 만든다.
금액 단위는 원(KRW), 모두 양수. 소득/지출은 tx_type 으로 구분.
재현성을 위해 random 은 고정 시드를 사용한다.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from server.core import categories as C


@dataclass
class MockTx:
    tx_date: date
    merchant: str
    amount: float
    category: str
    tx_type: str
    payment_method: str
    memo: str | None = None
    direction: str = "out"  # 송금 방향: out=보냄, in=받음 (정산 netting 용)


# --- baseline 후보 (정상 소비) ---
_MEALS = [
    ("학생식당", 4_500, C.FOOD),
    ("CU 강남점", 6_800, C.FOOD),
    ("GS25 후문점", 5_200, C.FOOD),
    ("김밥천국", 7_500, C.FOOD),
    ("맥도날드", 8_900, C.FOOD),
]
_CAFES = [
    ("메가커피", 2_500, C.CAFE),
    ("컴포즈커피", 2_900, C.CAFE),
    ("스타벅스 강남R점", 5_500, C.CAFE),
    ("이디야커피", 3_800, C.CAFE),
]
_DELIVERY = [
    ("배달의민족", 17_500, C.FOOD),
    ("요기요", 19_800, C.FOOD),
    ("쿠팡이츠", 21_300, C.FOOD),
    ("배달의민족", 15_400, C.FOOD),
]


def _pm_for(target_day: date, today: date, base: str = C.CHECK) -> str:
    """카드 사용 급증 시나리오: 최근 3주로 올수록 신용카드 비중을 높인다."""
    days_ago = (today - target_day).days
    rng = random.Random(target_day.toordinal() * 7 + 3)
    if days_ago <= 21 and rng.random() < 0.75:
        return C.CREDIT
    if days_ago <= 42 and rng.random() < 0.35:
        return C.CREDIT
    return base


def generate_mock_ledger(today: date) -> dict:
    """(profile, transactions) 를 담은 dict 반환."""
    rng = random.Random(20260813)
    txs: list[MockTx] = []
    start = today - timedelta(days=70)

    def month_first(d: date) -> date:
        return d.replace(day=1)

    # ---------------------------------------------------------------
    # 1) 정상 baseline: 식사/카페/교통 (요일 기반 반복)
    # ---------------------------------------------------------------
    d = start
    while d <= today:
        wd = d.weekday()  # 0=월 ... 6=일
        # 평일 등교 → 교통
        if wd < 5:
            txs.append(MockTx(d, "교통카드 충전", 1_450, C.TRANSPORT, C.EXPENSE,
                              _pm_for(d, today, C.CHECK), "대중교통"))
        # 식사: 주 4~5회
        if wd in (0, 1, 3, 4) or (wd == 5 and rng.random() < 0.5):
            m, a, cat = rng.choice(_MEALS)
            txs.append(MockTx(d, m, a + rng.randint(-500, 1500), cat, C.EXPENSE,
                              _pm_for(d, today)))
        # 카페: 주 3회
        if wd in (1, 3, 5):
            m, a, cat = rng.choice(_CAFES)
            txs.append(MockTx(d, m, a + rng.randint(-300, 800), cat, C.EXPENSE,
                              _pm_for(d, today)))
        d += timedelta(days=1)

    # 주말 배달(정상 주에는 주 1회 정도)
    d = start
    while d <= today - timedelta(days=7):  # 최근 주는 아래 시험기간 로직이 담당
        if d.weekday() == 6:  # 일요일
            m, a, cat = rng.choice(_DELIVERY)
            txs.append(MockTx(d, m, a, cat, C.EXPENSE, _pm_for(d, today), "배달"))
        d += timedelta(days=1)

    # ---------------------------------------------------------------
    # 6) 구독 서비스 증가 (점증): 넷플릭스(상시) → 스포티파이(2달전) → ChatGPT/쿠팡와우(이번달)
    # ---------------------------------------------------------------
    def add_monthly(merchant: str, day: int, amount: float, since: date):
        m = month_first(start)
        while m <= today:
            pay = m.replace(day=min(day, 28))
            if since <= pay <= today:
                txs.append(MockTx(pay, merchant, amount, C.SUBSCRIPTION, C.EXPENSE,
                                  _pm_for(pay, today, C.CREDIT), "구독 정기결제"))
            # 다음 달
            m = (m.replace(day=28) + timedelta(days=7)).replace(day=1)

    add_monthly("넷플릭스", 5, 13_500, start)                       # 상시
    add_monthly("유튜브 프리미엄", 8, 14_900, start)                 # 상시
    add_monthly("스포티파이", 12, 10_900, today - timedelta(days=55))  # 약 2달 전부터
    add_monthly("ChatGPT Plus", 3, 29_000, month_first(today))       # 이번 달 신규
    add_monthly("쿠팡 와우", 6, 7_890, month_first(today))           # 이번 달 신규

    # ---------------------------------------------------------------
    # 3) 여행: 지난달 중순 KTX + 숙소 (정상적인 일회성 spike)
    # ---------------------------------------------------------------
    trip = month_first(today) - timedelta(days=25)  # 대략 지난달 중순
    txs.append(MockTx(trip, "코레일 KTX", 47_800, C.TRANSPORT, C.EXPENSE, C.CREDIT, "부산 여행"))
    txs.append(MockTx(trip + timedelta(days=1), "야놀자 숙소", 132_000, C.TRAVEL, C.EXPENSE, C.CREDIT, "부산 여행"))
    txs.append(MockTx(trip + timedelta(days=1), "해운대 회센터", 68_000, C.FOOD, C.EXPENSE, C.CREDIT, "부산 여행"))
    txs.append(MockTx(trip + timedelta(days=2), "코레일 KTX", 47_800, C.TRANSPORT, C.EXPENSE, C.CREDIT, "부산 여행"))

    # ---------------------------------------------------------------
    # 4) 쇼핑 과소비: 지난달 말
    # ---------------------------------------------------------------
    shop = month_first(today) - timedelta(days=8)
    txs.append(MockTx(shop, "무신사", 89_000, C.SHOPPING, C.EXPENSE, C.CREDIT, "여름 옷"))
    txs.append(MockTx(shop + timedelta(days=1), "쿠팡", 42_300, C.SHOPPING, C.EXPENSE, C.CREDIT))
    txs.append(MockTx(shop + timedelta(days=2), "올리브영", 32_000, C.LIFE_BEAUTY, C.EXPENSE, C.CREDIT))

    # 교재 / 친구생일 / 공연 (다양성)
    txs.append(MockTx(start + timedelta(days=3), "교보문고", 38_500, C.EDUCATION, C.EXPENSE, C.CHECK, "전공 교재"))
    txs.append(MockTx(month_first(today) - timedelta(days=18), "카카오선물하기", 25_000, C.SHOPPING, C.EXPENSE, C.CREDIT, "친구 생일선물"))
    txs.append(MockTx(month_first(today) - timedelta(days=30), "인터파크티켓", 66_000, C.LEISURE, C.EXPENSE, C.CREDIT, "콘서트"))

    # ---------------------------------------------------------------
    # 2) 시험기간 배달 급증: 최근 7일(오늘 포함)
    # ---------------------------------------------------------------
    for i in range(7):
        day = today - timedelta(days=6 - i)
        # 거의 매일 배달 1~2회 (야식 포함)
        n = 2 if day.weekday() in (2, 4, 5, 6) else 1
        for _ in range(n):
            m, a, cat = rng.choice(_DELIVERY)
            txs.append(MockTx(day, m, a + rng.randint(0, 6000), cat, C.EXPENSE,
                              _pm_for(day, today, C.CREDIT), "시험기간 배달"))
        # 카페인 (시험기간 카페 증가)
        if day.weekday() in (0, 2, 4, 6):
            txs.append(MockTx(day, "스타벅스 강남R점", 6_100, C.CAFE, C.EXPENSE,
                              _pm_for(day, today, C.CREDIT), "시험기간"))

    # ---------------------------------------------------------------
    # 소득: 용돈/알바/장학금 (+ 7) 소득 감소)
    # ---------------------------------------------------------------
    def add_income(merchant: str, day: date, amount: float, cat: str):
        if start <= day <= today:
            txs.append(MockTx(day, merchant, amount, cat, C.INCOME, C.TRANSFER))

    # 용돈: 매월 1일 (이번 달은 소득 감소 → 축소)
    m = month_first(start)
    while m <= today:
        allowance = 300_000 if m == month_first(today) else 500_000  # 이번 달 감소
        add_income("부모님 용돈", m, allowance, C.ALLOWANCE)
        m = (m.replace(day=28) + timedelta(days=7)).replace(day=1)

    # 알바비: 매월 25일 (이번 달은 아직 미정산 + 근무 축소분 반영 위해 지난달까지)
    add_income("카페 알바비", month_first(today) - timedelta(days=18), 420_000, C.PART_TIME)
    add_income("카페 알바비", month_first(today) - timedelta(days=48), 460_000, C.PART_TIME)

    # 장학금: 일회성
    add_income("교내 성적장학금", month_first(today) - timedelta(days=20), 500_000, C.SCHOLARSHIP)

    # ---------------------------------------------------------------
    # 8) 친구 송금(정산 시나리오): 마스킹 이름 → 정산 대화 흐름 유도.
    #    일부는 내가 보냄(out), 일부는 친구가 입금(in). 같은 사람 보냄+받음 → netting 데모.
    # ---------------------------------------------------------------
    def add_transfer(merchant: str, day: date, amount: float, direction: str):
        if start <= day <= today:
            txs.append(MockTx(day, merchant, amount, C.ETC, C.TRANSFER,
                              C.TRANSFER, "친구 정산", direction))

    mf = month_first(today)
    add_transfer("토스 김*은", mf + timedelta(days=2), 12_000, "in")   # 내가 밥 사고 걔가 정산 입금
    add_transfer("박*서", mf + timedelta(days=4), 18_000, "out")       # 걔가 결제, 내가 송금
    add_transfer("이*준", mf + timedelta(days=6), 9_500, "in")
    add_transfer("최*아", mf + timedelta(days=7), 30_000, "out")       # 같이 큰 결제 내가 함
    add_transfer("최*아", mf + timedelta(days=8), 15_000, "in")        # 절반 돌려받음(netting)
    add_transfer("정*민", mf + timedelta(days=9), 22_000, "in")
    add_transfer("토스 김*은", mf - timedelta(days=20), 8_000, "in")   # 지난달 건(양감)
    add_transfer("한*결", mf - timedelta(days=15), 27_000, "out")

    # ---------------------------------------------------------------
    # 9) 규칙/AI 로도 애매한 '기타' 카드결제 → 분류 질문 흐름 유도 (규칙에 없는 상호명)
    # ---------------------------------------------------------------
    def add_eta(merchant: str, day: date, amount: float):
        if start <= day <= today:
            txs.append(MockTx(day, merchant, amount, C.ETC, C.EXPENSE,
                              _pm_for(day, today, C.CREDIT)))

    add_eta("다함컴퍼니", mf + timedelta(days=3), 5_500)
    add_eta("스튜디오 노아", mf - timedelta(days=5), 18_000)

    # 날짜순 정렬
    txs.sort(key=lambda t: t.tx_date)

    profile = {
        "name": "코니",
        "monthly_budget": 600_000,
        "card_billing_day": 14,
    }
    return {"profile": profile, "transactions": txs}
