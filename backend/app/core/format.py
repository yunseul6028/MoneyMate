"""친근한 금액 표기 (가독성).

원 단위 전체(324,207원) 대신 반올림해서 사람이 읽기 쉬운 형태로.
  - 10만원 이상: 만원 단위 반올림   → 681,324 → "68만원"
  - 1만~10만원: 천원 단위 반올림    → 76,190 → "7만 6천원"
  - 1만원 미만: 그대로(콤마)         → 8,500 → "8,500원"
의미가 남는 선에서만 반올림(금융정보 정확성 원칙과의 균형).
"""
from __future__ import annotations


def friendly_won(value: float | int | None) -> str:
    if value is None:
        return "—"
    n = round(value)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n < 10_000:
        return f"{sign}{n:,}원"
    if n < 100_000:
        r = round(n / 1000) * 1000
        man, cheon = r // 10_000, (r % 10_000) // 1000
        return f"{sign}{man}만 {cheon}천원" if cheon else f"{sign}{man}만원"
    man = round(n / 10_000)
    return f"{sign}{man}만원"
