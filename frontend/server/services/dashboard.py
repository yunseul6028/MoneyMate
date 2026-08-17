"""대시보드 요약 (STEP 11 UI 지원).

금융 건강 상태를 너무 복잡하지 않게 보여주기 위한 데이터 정리 + 한 줄 AI 요약.
한 줄 요약은 규칙기반(빠르고 안정적). 숫자는 전부 analysis 엔진 결과 그대로.
"""
from __future__ import annotations

from server.services.analysis import AnalysisReport


def one_liner(report: AnalysisReport) -> str:
    """대시보드 하단 한 줄 요약."""
    if report.top_categories_increase:
        c = report.top_categories_increase[0]
        return f"이번 달은 {c['category']} 지출이 평소보다 많이 늘었어."
    if report.categories:
        return f"이번 달은 {report.categories[0].category} 지출이 제일 많아."
    return "이번 달 소비는 대체로 평소랑 비슷해."


def build_dashboard(report: AnalysisReport, user_name: str) -> dict:
    d = report.to_dict()
    d["user"] = user_name
    d["one_liner"] = one_liner(report)
    return d
