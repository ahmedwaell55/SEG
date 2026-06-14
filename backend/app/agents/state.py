from typing import Any, TypedDict


class AnalysisState(TypedDict, total=False):
    raw_transcript: str
    cleaned_transcript: str
    speaker_report: dict[str, Any]
    sentiment_report: dict[str, Any]
    objection_report: dict[str, Any]
    prediction_report: dict[str, Any]
    recommendation_report: dict[str, Any]
    summary_report: dict[str, Any]
    final_report: dict[str, Any]

