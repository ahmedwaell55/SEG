from datetime import date
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models import BuyingSignal, Client, Meeting, NextAction, Objection, PainPoint, Recommendation
from app.schemas import MeetingProcessRequest
from app.services.serializers import serialize_meeting
from app.utils.transcript import clean_list, normalize_transcript
from app.workflows.meeting_analysis import analyze_transcript


class MeetingProcessingError(RuntimeError):
    pass


def _enum_to_text(value: Any) -> str:
    if hasattr(value, "value"):
        try:
            return str(value.value)
        except Exception:
            return str(value)
    return str(value)


def _normalize_report_item(item: Any, item_type: str) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        if item_type == "objection":
            objection = _enum_to_text(item.get("objection", "")).strip()
            category = _enum_to_text(item.get("category", "")).strip()
            severity = _enum_to_text(item.get("severity", "")).strip()
            evidence = _enum_to_text(item.get("verbatim_evidence", "")).strip()
            parts = [objection]
            if category:
                parts.append(f"Category: {category}")
            if severity:
                parts.append(f"Severity: {severity}")
            if evidence:
                parts.append(f'Evidence: "{evidence}"')
            return " | ".join(part for part in parts if part)
        if item_type == "buying_signal":
            signal = _enum_to_text(item.get("signal", "")).strip()
            category = _enum_to_text(item.get("category", "")).strip()
            strength = _enum_to_text(item.get("strength", "")).strip()
            evidence = _enum_to_text(item.get("verbatim_evidence", "")).strip()
            parts = [signal]
            if category:
                parts.append(f"Category: {category}")
            if strength:
                parts.append(f"Strength: {strength}")
            if evidence:
                parts.append(f'Evidence: "{evidence}"')
            return " | ".join(part for part in parts if part)
        pairs = []
        for key, value in item.items():
            text = _enum_to_text(value).strip()
            if text:
                pairs.append(f"{key}: {text}")
        return " | ".join(pairs)
    return _enum_to_text(item).strip()


def _normalize_report_list(values: Any, item_type: str) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        text = _normalize_report_item(value, item_type)
        if text:
            normalized.append(text)
    return clean_list(normalized)


def _add_items(db: Session, model, field_name: str, meeting_id: int, values: list[str]) -> None:  # noqa: ANN001
    for value in clean_list(values):
        db.add(model(meeting_id=meeting_id, **{field_name: value}))


def _speaker_notes(speaker_report: dict) -> str:
    sales = speaker_report.get("sales_speaker") or "Sales representative"
    client = speaker_report.get("client_speaker") or "Client"
    notes = speaker_report.get("speaker_notes") or "No speaker notes generated."
    return f"Sales speaker: {sales}. Client speaker: {client}. {notes}"


def _get_or_create_client(db: Session, payload: MeetingProcessRequest, user_id: int) -> Client:
    if payload.client_id is not None:
        client = db.query(Client).filter(Client.id == payload.client_id, Client.user_id == user_id).first()
        if client is None:
            raise MeetingProcessingError("Client not found")
        return client

    name = (payload.client_name or "").strip()
    phone = (payload.phone or "").strip()
    existing = db.query(Client).filter(Client.phone == phone, Client.user_id == user_id).first() if phone else None
    if existing:
        if name and existing.name != name:
            existing.name = name
            db.flush()
        return existing

    client = Client(name=name, phone=phone or "Not provided", user_id=user_id)
    db.add(client)
    db.flush()
    return client


def _apply_analysis_to_meeting(db: Session, meeting: Meeting, analysis: dict) -> None:
    import json
    report = analysis["report"]

    meeting.cleaned_transcript = analysis.get("cleaned_transcript")
    meeting.speaker_notes = _speaker_notes(analysis.get("speaker_report", {}))
    meeting.summary = report.get("summary")
    meeting.sentiment = report.get("sentiment")
    meeting.emotional_tone = report.get("emotional_tone")
    meeting.urgency_level = report.get("urgency_level")
    meeting.confidence_score = int(report.get("confidence_score") or 0)
    meeting.acceptance_probability = int(report.get("acceptance_probability") or 0)
    meeting.acceptance_label = report.get("acceptance_label")
    meeting.communication_style = report.get("communication_style")
    meeting.sales_strategy = report.get("sales_strategy")
    
    meeting.lead_stage = report.get("lead_stage")
    meeting.follow_up_strategy = report.get("follow_up_strategy")
    meeting.stakeholders = json.dumps(report.get("stakeholders", []))
    meeting.risks = json.dumps(report.get("risks", []))
    meeting.opportunities = json.dumps(report.get("opportunities", []))
    meeting.is_fallback = bool(report.get("is_fallback", False))

    meeting.objections.clear()
    meeting.pain_points.clear()
    meeting.recommendations.clear()
    meeting.buying_signals.clear()
    meeting.next_actions.clear()
    db.flush()

    _add_items(db, Objection, "objection_text", meeting.id, _normalize_report_list(report.get("objections", []), "objection"))
    _add_items(db, PainPoint, "pain_point_text", meeting.id, _normalize_report_list(report.get("pain_points", []), "pain_point"))
    _add_items(db, Recommendation, "recommendation_text", meeting.id, _normalize_report_list(report.get("recommendations", []), "recommendation"))
    _add_items(db, BuyingSignal, "signal_text", meeting.id, _normalize_report_list(report.get("buying_signals", []), "buying_signal"))
    _add_items(db, NextAction, "action_text", meeting.id, _normalize_report_list(report.get("next_steps", []), "next_step"))


async def process_meeting(db: Session, payload: MeetingProcessRequest, user_id: int) -> dict:
    transcript = normalize_transcript(payload.transcript)
    try:
        analysis = await analyze_transcript(transcript)
    except Exception as exc:
        raise MeetingProcessingError(f"LLM analysis failed: {exc}") from exc

    client = _get_or_create_client(db, payload, user_id)
    meeting = Meeting(
        client_id=client.id,
        meeting_date=payload.meeting_date or date.today(),
        transcript=transcript,
    )
    db.add(meeting)
    db.flush()
    _apply_analysis_to_meeting(db, meeting, analysis)
    from app.services.followup_service import create_or_refresh_followups_for_meeting

    await create_or_refresh_followups_for_meeting(db, meeting.id)

    db.commit()
    return get_meeting_payload(db, meeting.id, user_id=user_id)


async def reprocess_meeting(db: Session, meeting_id: int, user_id: int) -> dict:
    meeting = get_meeting(db, meeting_id, user_id=user_id)
    if meeting is None:
        raise MeetingProcessingError("Meeting not found")
    try:
        analysis = await analyze_transcript(meeting.transcript)
    except Exception as exc:
        raise MeetingProcessingError(f"LLM analysis failed: {exc}") from exc
    _apply_analysis_to_meeting(db, meeting, analysis)
    from app.services.followup_service import create_or_refresh_followups_for_meeting

    await create_or_refresh_followups_for_meeting(db, meeting.id)
    db.commit()
    return get_meeting_payload(db, meeting.id, user_id=user_id)


def get_meeting(db: Session, meeting_id: int, user_id: int | None = None) -> Meeting | None:
    query = (
        db.query(Meeting)
        .join(Client, Meeting.client_id == Client.id)
        .options(
            selectinload(Meeting.client),
            selectinload(Meeting.objections),
            selectinload(Meeting.pain_points),
            selectinload(Meeting.recommendations),
            selectinload(Meeting.buying_signals),
            selectinload(Meeting.next_actions),
        )
        .filter(Meeting.id == meeting_id)
    )
    if user_id is not None:
        query = query.filter(Client.user_id == user_id)
    return query.first()


def get_meeting_payload(db: Session, meeting_id: int, user_id: int | None = None) -> dict:
    meeting = get_meeting(db, meeting_id, user_id=user_id)
    if meeting is None:
        raise MeetingProcessingError("Meeting not found")
    return serialize_meeting(meeting)


def list_client_meetings(db: Session, client_id: int, user_id: int) -> list[dict]:
    meetings = (
        db.query(Meeting)
        .join(Client, Meeting.client_id == Client.id)
        .options(
            selectinload(Meeting.objections),
            selectinload(Meeting.pain_points),
            selectinload(Meeting.recommendations),
            selectinload(Meeting.buying_signals),
            selectinload(Meeting.next_actions),
        )
        .filter(Meeting.client_id == client_id, Client.user_id == user_id)
        .order_by(Meeting.meeting_date.desc(), Meeting.created_at.desc())
        .all()
    )
    return [serialize_meeting(meeting) for meeting in meetings]
