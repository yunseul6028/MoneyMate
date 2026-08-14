"""앱의 '오늘/지금' 단일 소스 (날짜 감각).

앱 어디서도 settings.demo_today 나 date.today() 를 직접 부르지 않는다.
날짜·시각이 필요하면 반드시 여기 today()/now() 를 통한다 → 데모/실시간 전환이 한 곳에서 끝난다.

  - live_date=False (기본): demo_today 로 고정 → 데모 재현성. 모든 계산·기록이 같은 날짜 위에 선다.
  - live_date=True: 실제 date.today() 사용 (실서비스 모드).

now() 는 today() 날짜에 '현재 시:분:초'를 얹는다 → 하루 안에서 시간 흐름(쿨다운 등)은 자연스럽게 유지.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.config import settings


def today() -> date:
    """앱이 인식하는 '오늘'."""
    return date.today() if settings.live_date else settings.demo_today


def now() -> datetime:
    """앱이 인식하는 '지금' (UTC). today() 날짜 + 실제 시각."""
    wall = datetime.now(timezone.utc)
    if settings.live_date:
        return wall
    d = settings.demo_today
    return wall.replace(year=d.year, month=d.month, day=d.day)


def is_demo() -> bool:
    return not settings.live_date
