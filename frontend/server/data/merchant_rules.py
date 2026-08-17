"""전역 가맹점 → 카테고리 규칙 (rule-based mapping).

STEP 7 분류기가 1순위로 사용한다. 처음 보는/애매한 가맹점만 LLM 으로 넘긴다.
키는 소문자·공백제거 후 '부분 포함'으로 매칭한다(app/services 분류기에서 처리).
"""
from __future__ import annotations

from server.core import categories as C

# merchant_key(정규화된 부분문자열) -> category
GLOBAL_MERCHANT_RULES: dict[str, str] = {
    # 편의점 / 식음료
    "cu": C.FOOD,
    "gs25": C.FOOD,
    "세븐일레븐": C.FOOD,
    "이마트24": C.FOOD,
    "김밥천국": C.FOOD,
    "맥도날드": C.FOOD,
    "버거킹": C.FOOD,
    "롯데리아": C.FOOD,
    "배달의민족": C.FOOD,
    "요기요": C.FOOD,
    "쿠팡이츠": C.FOOD,
    "학생식당": C.FOOD,
    "백반": C.FOOD,
    # 카페
    "스타벅스": C.CAFE,
    "starbucks": C.CAFE,
    "투썸": C.CAFE,
    "이디야": C.CAFE,
    "메가커피": C.CAFE,
    "컴포즈": C.CAFE,
    "빽다방": C.CAFE,
    "공차": C.CAFE,
    # 교통
    "교통카드": C.TRANSPORT,
    "지하철": C.TRANSPORT,
    "버스": C.TRANSPORT,
    "카카오t": C.TRANSPORT,
    "택시": C.TRANSPORT,
    "ktx": C.TRANSPORT,
    "코레일": C.TRANSPORT,
    "따릉이": C.TRANSPORT,
    # 쇼핑
    "쿠팡": C.SHOPPING,
    "무신사": C.SHOPPING,
    "지마켓": C.SHOPPING,
    "11번가": C.SHOPPING,
    "네이버쇼핑": C.SHOPPING,
    "에이블리": C.SHOPPING,
    "다이소": C.SHOPPING,
    # 생활/뷰티
    "올리브영": C.LIFE_BEAUTY,
    "다이소뷰티": C.LIFE_BEAUTY,
    "미용실": C.LIFE_BEAUTY,
    "약국": C.MEDICAL,
    "병원": C.MEDICAL,
    "의원": C.MEDICAL,
    # 교육
    "교보문고": C.EDUCATION,
    "알라딘": C.EDUCATION,
    "yes24": C.EDUCATION,
    "학원": C.EDUCATION,
    "인프런": C.EDUCATION,
    # 구독
    "넷플릭스": C.SUBSCRIPTION,
    "netflix": C.SUBSCRIPTION,
    "유튜브프리미엄": C.SUBSCRIPTION,
    "youtube": C.SUBSCRIPTION,
    "스포티파이": C.SUBSCRIPTION,
    "멜론": C.SUBSCRIPTION,
    "쿠팡와우": C.SUBSCRIPTION,
    "chatgpt": C.SUBSCRIPTION,
    "디즈니": C.SUBSCRIPTION,
    "왓챠": C.SUBSCRIPTION,
    # 여가
    "cgv": C.LEISURE,
    "메가박스": C.LEISURE,
    "롯데시네마": C.LEISURE,
    "노래방": C.LEISURE,
    "pc방": C.LEISURE,
    "볼링": C.LEISURE,
    "예스24공연": C.LEISURE,
    "인터파크티켓": C.LEISURE,
}
