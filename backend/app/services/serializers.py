import json
import re
import ast
from datetime import date
from typing import Any

from app.models import Client, Meeting


def _iso(value):
    return value.isoformat() if value else None


def _parse_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(item) for item in data]
    except Exception:
        pass
    return [item.strip() for item in value.split(",") if item.strip()]


def _enum_repr_cleanup(text: str) -> str:
    # Converts "<EnumName.X: 'Value'>" into "'Value'" for safer dict parsing.
    return re.sub(r"<[^:>]+:\s*'([^']+)'>", r"'\1'", text)


def _normalize_item_text(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        text = item.strip()
    else:
        text = str(item).strip()
    if not text:
        return ""
    text = _enum_repr_cleanup(text)
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                pairs = []
                for key, value in parsed.items():
                    value_text = str(value).strip()
                    if value_text:
                        pairs.append(f"{key}: {value_text}")
                if pairs:
                    return " | ".join(pairs)
        except Exception:
            pass
    return text


def _normalize_text_list(items: list[Any]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _normalize_item_text(item)
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
    return cleaned


def latest_meeting(client: Client) -> Meeting | None:
    meetings = list(client.meetings or [])
    if not meetings:
        return None
    return sorted(meetings, key=lambda item: (item.meeting_date or date.min, item.created_at), reverse=True)[0]


def serialize_meeting(meeting: Meeting) -> dict:
    return {
        "id": meeting.id,
        "client_id": meeting.client_id,
        "meeting_date": _iso(meeting.meeting_date),
        "transcript": meeting.transcript,
        "cleaned_transcript": meeting.cleaned_transcript,
        "speaker_notes": meeting.speaker_notes,
        "summary": meeting.summary,
        "sentiment": meeting.sentiment,
        "emotional_tone": meeting.emotional_tone,
        "urgency_level": meeting.urgency_level,
        "confidence_score": meeting.confidence_score,
        "acceptance_probability": meeting.acceptance_probability,
        "acceptance_label": meeting.acceptance_label,
        "communication_style": meeting.communication_style,
        "sales_strategy": meeting.sales_strategy,
        "lead_stage": meeting.lead_stage,
        "follow_up_strategy": meeting.follow_up_strategy,
        "stakeholders": _parse_list(meeting.stakeholders),
        "risks": _parse_list(meeting.risks),
        "opportunities": _parse_list(meeting.opportunities),
        "is_fallback": meeting.is_fallback,
        "pain_points": _normalize_text_list([item.pain_point_text for item in meeting.pain_points]),
        "objections": _normalize_text_list([item.objection_text for item in meeting.objections]),
        "recommendations": _normalize_text_list([item.recommendation_text for item in meeting.recommendations]),
        "buying_signals": _normalize_text_list([item.signal_text for item in meeting.buying_signals]),
        "next_steps": _normalize_text_list([item.action_text for item in meeting.next_actions]),
        "created_at": _iso(meeting.created_at),
        "updated_at": _iso(meeting.updated_at),
    }


def serialize_client_summary(client: Client) -> dict:
    latest = latest_meeting(client)
    return {
        "id": client.id,
        "name": client.name,
        "phone": client.phone,
        "meeting_count": len(client.meetings or []),
        "last_meeting_date": _iso(latest.meeting_date) if latest else None,
        "acceptance_probability": latest.acceptance_probability if latest else None,
        "acceptance_label": latest.acceptance_label if latest else None,
        "sentiment": latest.sentiment if latest else None,
        "lead_stage": latest.lead_stage if latest else None,
        "created_at": _iso(client.created_at),
        "updated_at": _iso(client.updated_at),
    }


def serialize_client_detail(client: Client) -> dict:
    return {
        **serialize_client_summary(client),
        "meetings": [serialize_meeting(meeting) for meeting in client.meetings],
    }
