from __future__ import annotations

import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.agents.llm import generate_agent_json
from app.models import Client, FollowUp, Meeting
from app.prompts.sales_prompts import followup_generation_prompt
from app.services.meeting_service import MeetingProcessingError
from app.services.serializers import serialize_meeting
from app.utils.transcript import fit_for_prompt

FOLLOWUP_SYSTEM_PROMPT = """
أنت مساعد متابعة مبيعات لوكالة تسويق رقمي. أنشئ 3 رسائل متابعة واتساب مخصصة للعميل.

قواعد إلزامية:
- اكتب جميع الرسائل والحقول النصية بالعربية الفصحى المهنية (ما عدا أسماء الخدمات الإنجليزية إن وُجدت).
- استخدم فقط الخدمات والأسعار والعروض من حقل company_knowledge_base في سياق CRM.
- الرسالة 1: تلخيص الاجتماع، معالجة اهتمام العميل، واقتراح خدمة محددة بسعر وعرض خصم من الكتالوج.
- الرسالة 2: معالجة الاعتراضات بقيمة ملموسة — اذكر خصمًا أو عرضًا مناسبًا من الكتالوج.
- الرسالة 3: إثارة اهتمام بعرض محدود أو باقة مرتبطة، وشجّع العميل على الرد والاستمرار في المحادثة.
- نبرة احترافية، مقنعة، ودية. الطول: 50–120 كلمة لكل رسالة.
- لا تخترع خدمات أو أسعارًا غير موجودة في الكتالوج أو المحادثة.
- أعد JSON صالحًا فقط.

المخطط:
{
  "followups": [
    {
      "follow_up_number": 1,
      "priority_level": "High|Medium|Low",
      "objective": "string",
      "communication_tone": "string",
      "whatsapp_message": "string",
      "transcript_evidence": "string"
    }
  ]
}
""".strip()


def _as_utc_start(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _status_for_datetime(scheduled_at: datetime, completed_at: datetime | None) -> str:
    if completed_at:
        return "Completed"
    now = datetime.now(UTC).date()
    date_value = _as_utc_start(scheduled_at).date()
    if date_value == now:
        return "Due Today"
    return "Upcoming"


def _preview(message: str | None) -> str:
    text = (message or "").strip()
    if len(text) <= 130:
        return text
    return text[:127].rstrip() + "..."


def _format_riyal(value: float) -> str:
    return f"{value:,.2f}"


def _message_includes_catalog(message: str, matches: list[Any]) -> bool:
    """True when the message cites catalog pricing (riyal + amounts + service name)."""
    from app.services.service_search import ServiceMatch

    text = (message or "").strip()
    if not text or "ريال" not in text or not re.search(r"\d{3,}", text):
        return False
    for match in matches:
        if isinstance(match, ServiceMatch) and match.service.arabic_name in text:
            return True
    return False


def build_catalog_followup_messages(
    meeting: Meeting,
    matches: list[Any],
) -> list[dict[str, Any]]:
    """Deterministic Arabic follow-ups grounded in matched catalog services."""
    from app.services.service_search import ServiceMatch

    client_name = meeting.client.name
    tone = meeting.communication_style or "استشاري وواضح"
    evidence = meeting.summary or "اهتمام العميل بخدمات النمو الرقمي."

    typed_matches = [m for m in matches if isinstance(m, ServiceMatch)]
    if not typed_matches:
        return _fallback_followups(meeting)

    primary = typed_matches[0].service
    secondary = typed_matches[1].service if len(typed_matches) > 1 else primary
    bundle = typed_matches[2].service if len(typed_matches) > 2 else secondary

    related_note = ""
    if primary.related_services:
        related_note = f" كما يمكن دمجها مع {primary.related_services[0]}."

    return [
        {
            "follow_up_number": 1,
            "priority_level": "High",
            "objective": f"تقديم {primary.arabic_name} بسعر وعرض خصم واضحين.",
            "communication_tone": tone,
            "whatsapp_message": (
                f"مرحبًا {client_name}، شكرًا على اجتماعنا! "
                f"بناءً على اهتمامك بـ{primary.arabic_name}، يسعدني مشاركتك العرض: "
                f"السعر الأساسي {_format_riyal(primary.base_price)} ريال، "
                f"أو بخصم 15% بـ{_format_riyal(primary.discount_15)} ريال "
                f"(توفير {_format_riyal(primary.base_price - primary.discount_15)} ريال).{related_note} "
                f"هل يناسبك موعد قصير هذا الأسبوع لمراجعة التفاصيل؟"
            ),
            "transcript_evidence": evidence,
        },
        {
            "follow_up_number": 2,
            "priority_level": "Medium",
            "objective": f"معالجة التردد بقيمة ملموسة لـ{secondary.arabic_name}.",
            "communication_tone": tone,
            "whatsapp_message": (
                f"أهلًا {client_name}، أتابع معك بخصوص {secondary.arabic_name}. "
                f"لدينا عرض خصم 20% بـ{_format_riyal(secondary.discount_20)} ريال "
                f"بدلًا من {_format_riyal(secondary.base_price)} ريال — "
                f"مناسب لبدء التنفيذ بسرعة وبعائد أوضح. "
                f"هل تحبين مكالمة 15 دقيقة لشرح الخطة؟"
            ),
            "transcript_evidence": evidence,
        },
        {
            "follow_up_number": 3,
            "priority_level": "High",
            "objective": "حث القرار بعرض محدود وباقة مكملة.",
            "communication_tone": tone,
            "whatsapp_message": (
                f"مرحبًا {client_name}، اقتراح خاص: دمج {primary.arabic_name} مع {bundle.arabic_name} "
                f"بسعر {_format_riyal(primary.discount_15)} + {_format_riyal(bundle.discount_10)} ريال "
                f"لتسريع النمو والظهور. العرض متاح لفترة محدودة — "
                f"هل نكمل المحادثة اليوم لحجز الخطوة التالية؟"
            ),
            "transcript_evidence": evidence,
        },
    ]


def _fallback_followups(meeting: Meeting) -> list[dict[str, Any]]:
    objective_base = "تعزيز القيمة ومعالجة الاعتراضات بخطوة تالية واضحة."
    tone = meeting.communication_style or "استشاري وواضح"
    evidence = meeting.summary or "طلب العميل خطوات عملية تالية."
    client_name = meeting.client.name
    return [
        {
            "follow_up_number": 1,
            "priority_level": "High",
            "objective": "مشاركة المواد الموعودة وتأكيد موعد متابعة قصير.",
            "communication_tone": tone,
            "whatsapp_message": (
                f"مرحبًا {client_name}، شكرًا على وقتك في اجتماعنا. "
                "أشاركك ملخصًا سريعًا لأولوياتك والخطوة التالية المناسبة لاحتياجك. "
                "هل يناسبك تحديد موعد قصير هذا الأسبوع لمتابعة التفاصيل؟"
            ),
            "transcript_evidence": evidence,
        },
        {
            "follow_up_number": 2,
            "priority_level": "Medium",
            "objective": objective_base,
            "communication_tone": tone,
            "whatsapp_message": (
                f"أهلًا {client_name}، أتابع معك بعرض يربط احتياجك بقيمة ملموسة وخطة تنفيذ واضحة. "
                "يسعدني توضيح العرض والأسعار في اتصال قصير لا يتجاوز 20 دقيقة."
            ),
            "transcript_evidence": evidence,
        },
        {
            "follow_up_number": 3,
            "priority_level": "High",
            "objective": "حث العميل على اتخاذ قرار ومتابعة المحادثة.",
            "communication_tone": tone,
            "whatsapp_message": (
                f"مرحبًا {client_name}، أود التأكد من جاهزيتكم لخطوة القرار. "
                "أجهّز لكم خطة مختصرة تشمل العرض والجدول الزمني — هل نكمل المحادثة اليوم؟"
            ),
            "transcript_evidence": evidence,
        },
    ]


def _normalize_level(value: Any, default: str = "Medium") -> str:
    text = str(value or default).strip().lower()
    if text == "high":
        return "High"
    if text == "low":
        return "Low"
    return "Medium"


def _normalize_followup_payload(
    raw: dict[str, Any],
    meeting: Meeting,
    matches: list[Any] | None = None,
) -> list[dict[str, Any]]:
    catalog_messages = build_catalog_followup_messages(meeting, matches or [])
    catalog_by_number = {item["follow_up_number"]: item for item in catalog_messages}

    items = raw.get("followups")
    if not isinstance(items, list) or len(items) < 3:
        return catalog_messages

    result: list[dict[str, Any]] = []
    for expected_number in (1, 2, 3):
        source = next(
            (item for item in items if isinstance(item, dict) and int(item.get("follow_up_number", 0)) == expected_number),
            None,
        )
        if source is None:
            source = {}
        llm_message = str(source.get("whatsapp_message") or "").strip()
        catalog_item = catalog_by_number.get(expected_number, {})
        uses_catalog = _message_includes_catalog(llm_message, matches or [])
        if not llm_message or not uses_catalog:
            llm_message = catalog_item.get("whatsapp_message") or llm_message

        result.append(
            {
                "follow_up_number": expected_number,
                "priority_level": _normalize_level(source.get("priority_level")),
                "objective": str(source.get("objective") or "").strip()
                or catalog_item.get("objective")
                or "تقدم الصفقة بخطوة تالية واضحة.",
                "communication_tone": str(source.get("communication_tone") or meeting.communication_style or "استشاري").strip(),
                "whatsapp_message": llm_message,
                "transcript_evidence": str(source.get("transcript_evidence") or meeting.summary or "").strip(),
            }
        )
    return result


def _priority_from_probability(probability: int | None) -> str:
    value = int(probability or 0)
    if value >= 75:
        return "High"
    if value >= 45:
        return "Medium"
    return "Low"


def _schedule_times(base_date: datetime) -> list[datetime]:
    base = _as_utc_start(base_date)
    # 3 follow-ups distributed across 15 days
    offsets = [3, 8, 15]
    scheduled = []
    for offset in offsets:
        date_value = (base + timedelta(days=offset)).date()
        scheduled.append(datetime.combine(date_value, time(hour=10, minute=0, tzinfo=UTC)))
    return scheduled


def _meeting_context(meeting: Meeting) -> dict[str, Any]:
    payload = serialize_meeting(meeting)
    return {
        "client_name": meeting.client.name,
        "meeting_date": payload.get("meeting_date"),
        "summary": payload.get("summary"),
        "sentiment": payload.get("sentiment"),
        "lead_stage": payload.get("lead_stage"),
        "acceptance_probability": payload.get("acceptance_probability"),
        "objections": payload.get("objections"),
        "pain_points": payload.get("pain_points"),
        "buying_signals": payload.get("buying_signals"),
        "next_steps": payload.get("next_steps"),
        "transcript_excerpt": fit_for_prompt(payload.get("transcript") or "", 7000),
    }


async def _generate_followup_content(meeting: Meeting) -> list[dict[str, Any]]:
    import logging

    from app.services.service_search import (
        detect_services_from_conversation,
        format_catalog_context,
    )

    logger = logging.getLogger("ai_closer.followup")

    pain_points = [p.pain_point_text for p in meeting.pain_points] if meeting.pain_points else []
    objections = [o.objection_text for o in meeting.objections] if meeting.objections else []
    buying_signals = [b.signal_text for b in meeting.buying_signals] if meeting.buying_signals else []
    transcript_excerpt = _meeting_context(meeting).get("transcript_excerpt") or ""

    matches = detect_services_from_conversation(
        transcript=transcript_excerpt,
        summary=meeting.summary or "",
        pain_points=pain_points,
        objections=objections,
        buying_signals=buying_signals,
        top_k=3,
    )
    company_context = format_catalog_context(matches)
    catalog_followups = build_catalog_followup_messages(meeting, matches)
    fallback = {"followups": catalog_followups}

    if matches:
        logger.info(
            "Matched service for follow-ups: %s (score=%.1f)",
            matches[0].service.arabic_name,
            matches[0].score,
        )
    else:
        logger.warning("No service match from catalog — using generic fallback")

    context = _meeting_context(meeting)
    context["company_knowledge_base"] = company_context
    if matches:
        context["primary_service"] = matches[0].service.arabic_name
        context["related_services"] = [m.service.arabic_name for m in matches[1:]]

    response = await generate_agent_json(
        FOLLOWUP_SYSTEM_PROMPT,
        followup_generation_prompt(context),
        fallback,
    )
    return _normalize_followup_payload(response, meeting, matches)


async def create_or_refresh_followups_for_meeting(db: Session, meeting_id: int) -> list[FollowUp]:
    meeting = (
        db.query(Meeting)
        .options(
            selectinload(Meeting.client),
            selectinload(Meeting.objections),
            selectinload(Meeting.pain_points),
            selectinload(Meeting.buying_signals),
            selectinload(Meeting.next_actions),
            selectinload(Meeting.recommendations),
        )
        .filter(Meeting.id == meeting_id)
        .first()
    )
    if meeting is None:
        raise MeetingProcessingError("Meeting not found for follow-up generation")

    db.query(FollowUp).filter(FollowUp.meeting_id == meeting_id).delete()
    db.flush()

    generated = await _generate_followup_content(meeting)
    schedule = _schedule_times(datetime.combine(meeting.meeting_date, time(hour=9, minute=0, tzinfo=UTC)))
    default_priority = _priority_from_probability(meeting.acceptance_probability)

    created: list[FollowUp] = []
    for idx, slot in enumerate(schedule, start=1):
        source = generated[idx - 1] if idx - 1 < len(generated) else {}
        followup = FollowUp(
            meeting_id=meeting.id,
            client_id=meeting.client_id,
            follow_up_number=idx,
            scheduled_at=slot,
            status=_status_for_datetime(slot, None),
            priority_level=_normalize_level(source.get("priority_level"), default_priority),
            objective=str(source.get("objective") or "متابعة الصفقة بخطوة عملية.").strip(),
            communication_tone=str(source.get("communication_tone") or meeting.communication_style or "استشاري").strip(),
            whatsapp_message=str(source.get("whatsapp_message") or "").strip(),
            transcript_evidence=str(source.get("transcript_evidence") or meeting.summary or "").strip(),
        )
        db.add(followup)
        created.append(followup)

    db.flush()
    return created


def _serialize_followup(followup: FollowUp) -> dict[str, Any]:
    meeting = followup.meeting
    client = followup.client
    scheduled = _as_utc_start(followup.scheduled_at)
    status = _status_for_datetime(scheduled, followup.completed_at)
    now_date = datetime.now(UTC).date()
    days_remaining = (scheduled.date() - now_date).days
    return {
        "id": followup.id,
        "client_id": followup.client_id,
        "client_name": client.name if client else "Unknown Client",
        "client_phone": client.phone if client else None,
        "meeting_id": followup.meeting_id,
        "meeting_summary": meeting.summary if meeting else None,
        "deal_probability": meeting.acceptance_probability if meeting else None,
        "lead_stage": meeting.lead_stage if meeting else None,
        "follow_up_number": followup.follow_up_number,
        "scheduled_at": scheduled.isoformat(),
        "status": status,
        "days_remaining": days_remaining,
        "priority_level": followup.priority_level,
        "whatsapp_preview": _preview(followup.whatsapp_message),
        "whatsapp_message": followup.whatsapp_message,
        "follow_up_objective": followup.objective,
        "communication_tone": followup.communication_tone,
        "transcript_evidence": followup.transcript_evidence,
        "completed_at": followup.completed_at.isoformat() if followup.completed_at else None,
        "created_at": followup.created_at.isoformat() if followup.created_at else None,
        "updated_at": followup.updated_at.isoformat() if followup.updated_at else None,
    }


def list_followups(db: Session, user_id: int, status: str | None = None) -> dict[str, Any]:
    query = (
        db.query(FollowUp)
        .join(Client, FollowUp.client_id == Client.id)
        .options(selectinload(FollowUp.client), selectinload(FollowUp.meeting))
        .filter(Client.user_id == user_id)
        .order_by(FollowUp.scheduled_at.asc(), FollowUp.follow_up_number.asc())
    )
    if status:
        normalized = status.strip().lower()
        if normalized == "completed":
            query = query.filter(FollowUp.completed_at.isnot(None))
        elif normalized in {"due today", "due_today"}:
            today = datetime.now(UTC).date()
            query = query.filter(FollowUp.completed_at.is_(None)).filter(FollowUp.scheduled_at >= datetime.combine(today, time.min, tzinfo=UTC)).filter(
                FollowUp.scheduled_at <= datetime.combine(today, time.max, tzinfo=UTC)
            )
        elif normalized == "upcoming":
            today = datetime.now(UTC).date()
            query = query.filter(FollowUp.completed_at.is_(None)).filter(FollowUp.scheduled_at > datetime.combine(today, time.max, tzinfo=UTC))

    items = [_serialize_followup(item) for item in query.all()]
    due_today = [item for item in items if item["status"] == "Due Today"]
    upcoming = [item for item in items if item["status"] == "Upcoming"]
    completed = [item for item in items if item["status"] == "Completed"]
    nearest = sorted([item for item in items if item["status"] != "Completed"], key=lambda x: x["scheduled_at"])[:3]

    return {
        "items": items,
        "nearest": nearest,
        "due_today": due_today,
        "upcoming": upcoming,
        "completed": completed,
    }


def get_followup(db: Session, followup_id: int, user_id: int) -> dict[str, Any]:
    followup = (
        db.query(FollowUp)
        .join(Client, FollowUp.client_id == Client.id)
        .options(selectinload(FollowUp.client), selectinload(FollowUp.meeting))
        .filter(FollowUp.id == followup_id, Client.user_id == user_id)
        .first()
    )
    if followup is None:
        raise MeetingProcessingError("Follow-up not found")
    return _serialize_followup(followup)


def update_followup_status(db: Session, followup_id: int, status: str, user_id: int) -> dict[str, Any]:
    followup = (
        db.query(FollowUp)
        .join(Client, FollowUp.client_id == Client.id)
        .filter(FollowUp.id == followup_id, Client.user_id == user_id)
        .first()
    )
    if followup is None:
        raise MeetingProcessingError("Follow-up not found")
    normalized = status.strip()
    if normalized == "Completed":
        followup.completed_at = datetime.now(UTC)
    else:
        followup.completed_at = None
    followup.status = normalized
    db.commit()
    return get_followup(db, followup_id, user_id=user_id)


async def regenerate_followup_message(db: Session, followup_id: int, user_id: int) -> dict[str, Any]:
    followup = (
        db.query(FollowUp)
        .join(Client, FollowUp.client_id == Client.id)
        .options(
            selectinload(FollowUp.client),
            selectinload(FollowUp.meeting).selectinload(Meeting.objections),
            selectinload(FollowUp.meeting).selectinload(Meeting.pain_points),
            selectinload(FollowUp.meeting).selectinload(Meeting.buying_signals),
            selectinload(FollowUp.meeting).selectinload(Meeting.next_actions),
            selectinload(FollowUp.meeting).selectinload(Meeting.recommendations),
        )
        .filter(FollowUp.id == followup_id, Client.user_id == user_id)
        .first()
    )
    if followup is None:
        raise MeetingProcessingError("Follow-up not found")

    generated = await _generate_followup_content(followup.meeting)
    chosen = next((item for item in generated if item["follow_up_number"] == followup.follow_up_number), generated[0])
    followup.priority_level = _normalize_level(chosen.get("priority_level"), followup.priority_level)
    followup.objective = chosen.get("objective") or followup.objective
    followup.communication_tone = chosen.get("communication_tone") or followup.communication_tone
    followup.whatsapp_message = chosen.get("whatsapp_message") or followup.whatsapp_message
    followup.transcript_evidence = chosen.get("transcript_evidence") or followup.transcript_evidence
    db.commit()
    return get_followup(db, followup_id, user_id=user_id)
