import json
from typing import Any
from app.agents.llm import generate_agent_json
from app.agents.state import AnalysisState
from app.config import get_settings
from app.prompts.sales_prompts import (
    FULL_ANALYSIS_SYSTEM,
    TRANSCRIPT_CLEANER_SYSTEM,
    SalesIntelligenceOutput,
    full_analysis_prompt,
    transcript_prompt,
    LeadStageEnum,
)
from app.utils.transcript import chunk_text, clean_list, fit_for_prompt, normalize_transcript
from app.utils.validators import (
    generate_fallback_response_with_flags,
    validate_json_structure,
)


def _enum_to_text(value: Any) -> str:
    if hasattr(value, "value"):
        try:
            return str(value.value)
        except Exception:
            return str(value)
    return str(value)


def _stringify_structured_item(item: Any, item_type: str) -> str:
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

        raw_parts: list[str] = []
        for key, value in item.items():
            text = _enum_to_text(value).strip()
            if text:
                raw_parts.append(f"{key}: {text}")
        return " | ".join(raw_parts)

    return _enum_to_text(item).strip()


def _normalize_structured_list(values: Any, item_type: str, max_items: int = 12) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized = []
    for item in values:
        text = _stringify_structured_item(item, item_type)
        if text:
            normalized.append(text)
    return clean_list(normalized, max_items=max_items)


def calculate_deal_probability(response: dict) -> tuple[int, str]:
    """
    Deterministic scoring engine based on concrete sales indicators extracted by the AI agent.
    Avoids arbitrary model hallucinations and implements standard B2B conversion mathematics.
    """
    # Start with a baseline qualification probability
    score = 30

    # 1. Lead Qualification Stage (Max +25 points) - Updated for new enum-based stages
    stage = str(response.get("lead_stage_assessment", {}).get("stage") or "Qualified").lower()
    if "near closing" in stage or "closing" in stage:
        score += 25
    elif "negotiation" in stage:
        score += 20
    elif "sql" in stage:
        score += 15
    elif "qualified" in stage:
        score += 10
    elif "interested" in stage:
        score += 5
    else:  # Cold
        score += 0

    # 2. Urgency Level (Max +15 points)
    urgency = str(response.get("urgency_level") or "Medium").lower()
    if "high" in urgency:
        score += 15
    elif "medium" in urgency:
        score += 8
    else:
        score += 2

    # 3. Client Sentiment (Max +15 points / -15 penalty) - Updated for nuanced sentiment
    sentiment_assessment = response.get("sentiment_assessment", {})
    sentiment = str(sentiment_assessment.get("sentiment") or "Neutral").lower()
    if "positive" in sentiment:
        score += 15
    elif "cautiously optimistic" in sentiment:
        score += 10
    elif "neutral" in sentiment:
        score += 5
    elif "cautiously pessimistic" in sentiment:
        score -= 5
    else:  # negative client response
        score -= 15

    # 4. Stakeholder Presence & Buying Committee (Max +10 points)
    stakeholders = [s.lower() for s in response.get("stakeholders", [])]
    has_decision_makers = any(
        any(role in s for role in ["ceo", "director", "manager", "cfo", "vp", "owner", "finance"])
        for s in stakeholders
    )
    if has_decision_makers:
        score += 10

    # 5. Buying Signals Count (Max +15 points) - Handle new signal structure
    signals = response.get("buying_signals") or []
    signal_count = len(signals)
    if signal_count >= 4:
        score += 15
    elif signal_count >= 2:
        score += 8
    elif signal_count >= 1:
        score += 4

    # 6. Strong Buying Signal Strength (Max +10 points)
    strong_signals = sum(1 for s in signals if isinstance(s, dict) and s.get("strength") == "Strong")
    if strong_signals >= 2:
        score += 10
    elif strong_signals == 1:
        score += 5

    # 7. Discussed ROI / Efficiency / Business Value (Max +10 points)
    signals_text = []
    for s in signals:
        if isinstance(s, dict):
            signals_text.append(s.get("signal", ""))
        else:
            signals_text.append(str(s))
    
    next_steps_blob = " ".join(response.get("next_steps", [])).lower()
    signals_blob = " ".join(signals_text).lower()
    if any(term in (signals_blob + next_steps_blob) for term in ["roi", "case stud", "efficiency", "savings", "value"]):
        score += 10

    # 8. Objection Friction (Max -10 points penalty)
    objections = response.get("objections") or []
    risks = response.get("risks") or []
    
    objection_text = []
    for o in objections:
        if isinstance(o, dict):
            objection_text.append(o.get("objection", "").lower())
        else:
            objection_text.append(str(o).lower())
    
    risk_text = [r.lower() for r in risks]
    
    has_budget_objection = any(
        any(term in text for term in ["budget", "price", "pricing", "expensive", "cost"])
        for text in (objection_text + risk_text)
    )
    if has_budget_objection:
        score -= 10

    # 9. Technical / Integration friction (Max -5 points penalty)
    has_tech_objection = any(
        any(term in text for term in ["integration", "legacy", "security", "technical", "it manager"])
        for text in (objection_text + risk_text)
    )
    if has_tech_objection:
        score -= 5

    # 10. Implementation / Adoption fears (Max -5 points penalty)
    has_adoption_objection = any(
        any(term in text for term in ["adopt", "resist", "slow", "onboard", "complicate"])
        for text in (objection_text + risk_text)
    )
    if has_adoption_objection:
        score -= 5

    # 11. Engagement & Continuation Signals (Max +15 points)
    has_followup_agreed = any(
        any(term in next_steps_blob for term in ["schedule", "workshop", "meeting", "follow-up", "next week"])
        for term in ["schedule", "workshop", "meeting", "follow-up"]
    )
    if has_followup_agreed or "timeline" in next_steps_blob:
        score += 15

    # Clamp probability to a logical B2B range: 5% to 98%
    clamped_score = max(5, min(98, score))

    if clamped_score >= 75:
        label = "High"
    elif clamped_score >= 45:
        label = "Medium"
    else:
        label = "Low"

    return clamped_score, label


def _cleaner_fallback(chunk: str) -> dict:
    return {"cleaned_transcript": chunk}


def _analysis_fallback(transcript: str) -> dict:
    """Enhanced fallback with is_fallback flag and proper structure."""
    return generate_fallback_response_with_flags()


async def transcript_cleaner_agent(state: AnalysisState) -> AnalysisState:
    settings = get_settings()
    raw = normalize_transcript(state["raw_transcript"])
    cleaned_chunks: list[str] = []
    for chunk in chunk_text(raw, settings.max_transcript_chunk_chars):
        fallback = _cleaner_fallback(chunk)
        response = await generate_agent_json(
            TRANSCRIPT_CLEANER_SYSTEM,
            transcript_prompt(chunk),
            fallback,
        )
        cleaned_chunks.append(
            str(response.get("cleaned_transcript") or fallback["cleaned_transcript"]).strip()
        )
    return {"cleaned_transcript": "\n\n".join(part for part in cleaned_chunks if part)}


async def full_analysis_agent(state: AnalysisState) -> AnalysisState:
    """Rigorous sales analysis node applying strict Pydantic model validation and the deterministic scoring engine."""
    transcript = fit_for_prompt(state["cleaned_transcript"], get_settings().max_prompt_chars)
    fallback = _analysis_fallback(transcript)
    
    from app.services.service_search import detect_services_from_conversation, format_catalog_context

    matches = detect_services_from_conversation(transcript=transcript[:7000], top_k=3)
    company_context = format_catalog_context(matches)

    enriched_transcript = (
        f"{transcript}\n\n"
        f"كتالوج الخدمات والأسعار (استخدمه في التوصيات والاستراتيجية والخطوات التالية):\n"
        f"{company_context}"
    )
    
    # Trigger LLM query with robust manual validation & error feedback auto-retry loop
    response = await generate_agent_json(
        FULL_ANALYSIS_SYSTEM,
        full_analysis_prompt(enriched_transcript),
        fallback,
    )

    # Post-process and validate output structure
    response = validate_json_structure(response)

    # Apply deterministic scoring engine in Python (avoids model hallucinating deal metrics)
    prob, label = calculate_deal_probability(response)
    
    conf = int(response.get("confidence_score") or 60)
    conf = max(0, min(100, conf))
    is_fallback = response.get("is_fallback", False)

    # Parse sentiment assessment safely
    sentiment_assessment = response.get("sentiment_assessment", {})
    sentiment = sentiment_assessment.get("sentiment", "Neutral")
    emotional_tone = sentiment_assessment.get("emotional_tone", "Neutral")
    sentiment_drivers = sentiment_assessment.get("sentiment_drivers", [])

    # Parse lead stage assessment safely
    lead_stage_assessment = response.get("lead_stage_assessment", {})
    lead_stage = lead_stage_assessment.get("stage", "Qualified")
    stage_confidence = lead_stage_assessment.get("stage_confidence", 60)
    stage_signals = lead_stage_assessment.get("stage_signals", [])
    stage_blockers = lead_stage_assessment.get("stage_blockers", [])

    # Parse list fields safely
    stakeholders = clean_list(response.get("stakeholders", []), max_items=12)
    risks = clean_list(response.get("risks", []), max_items=12)
    opportunities = clean_list(response.get("opportunities", []), max_items=12)
    objections = _normalize_structured_list(response.get("objections", []), "objection", max_items=12)
    buying_signals = _normalize_structured_list(response.get("buying_signals", []), "buying_signal", max_items=12)

    return {
        "speaker_report": {
            "sales_speaker": response.get("sales_speaker", "Sales Representative"),
            "client_speaker": response.get("client_speaker", "Client Representative"),
            "speaker_notes": f"Stakeholders identified: {', '.join(stakeholders) if stakeholders else 'None identified'}",
            "client_quotes": clean_list(response.get("client_quotes", []), max_items=6),
        },
        "sentiment_report": {
            "sentiment": sentiment,
            "emotional_tone": emotional_tone,
            "sentiment_drivers": sentiment_drivers,
            "sentiment_confidence": sentiment_assessment.get("sentiment_confidence", conf),
            "hesitation_level": "High" if len(objections) > 2 else "Low",
            "urgency_level": str(response.get("urgency_level", "Medium")),
            "buying_intent": label,
            "confidence_score": conf,
            "is_fallback": is_fallback,
            "evidence": [],
        },
        "lead_stage_report": {
            "stage": lead_stage,
            "stage_confidence": stage_confidence,
            "stage_signals": stage_signals,
            "stage_blockers": stage_blockers,
            "advancement_timeline": lead_stage_assessment.get("advancement_timeline"),
            "is_fallback": is_fallback,
        },
        "objection_report": {
            "objections": objections,
            "pain_points": clean_list(response.get("pain_points", []), max_items=12),
            "buying_signals": buying_signals,
            "blockers": risks,
            "is_fallback": is_fallback,
        },
        "prediction_report": {
            "acceptance_probability": prob,
            "acceptance_label": label,
            "confidence_score": conf,
            "reasoning": "Calculated using signals scorecard.",
            "is_fallback": is_fallback,
        },
        "recommendation_report": {
            "recommendations": clean_list(response.get("recommendations", []), max_items=12),
            "next_steps": clean_list(response.get("next_steps", []), max_items=12),
            "communication_style": response.get("communication_style", "Consultative"),
            "sales_strategy": response.get("sales_strategy", "Unspecified"),
            "is_fallback": is_fallback,
        },
        "summary_report": {
            "summary": response.get("summary", "Analysis complete"),
            "key_points": clean_list(response.get("key_points", []), max_items=12),
            "is_fallback": is_fallback,
        },
        "final_report": {
            "summary": response.get("summary", "Analysis complete"),
            "sentiment": sentiment,
            "emotional_tone": emotional_tone,
            "sentiment_drivers": sentiment_drivers,
            "urgency_level": str(response.get("urgency_level", "Medium")),
            "confidence_score": conf,
            "pain_points": clean_list(response.get("pain_points", []), max_items=12),
            "objections": objections,
            "buying_signals": buying_signals,
            "acceptance_probability": prob,
            "acceptance_label": label,
            "recommendations": clean_list(response.get("recommendations", []), max_items=12),
            "next_steps": clean_list(response.get("next_steps", []), max_items=12),
            "communication_style": response.get("communication_style", "Consultative"),
            "sales_strategy": response.get("sales_strategy", "Unspecified"),
            "lead_stage": lead_stage,
            "stage_confidence": stage_confidence,
            "stage_signals": stage_signals,
            "stage_blockers": stage_blockers,
            "follow_up_strategy": response.get("follow_up_strategy", "Follow up with discovery questions"),
            "stakeholders": stakeholders,
            "risks": risks,
            "opportunities": opportunities,
            "key_points": clean_list(response.get("key_points", []), max_items=12),
            "is_fallback": is_fallback,
        },
    }


# ── Compat Stubs Kept to Avoid Import Errors ──────────────────────────────────
async def speaker_detection_agent(state: AnalysisState) -> AnalysisState: return state
async def sentiment_analysis_agent(state: AnalysisState) -> AnalysisState: return state
async def objection_extraction_agent(state: AnalysisState) -> AnalysisState: return state
async def deal_prediction_agent(state: AnalysisState) -> AnalysisState: return state
async def recommendation_agent(state: AnalysisState) -> AnalysisState: return state
async def summary_agent(state: AnalysisState) -> AnalysisState: return state
async def final_report_generator_agent(state: AnalysisState) -> AnalysisState: return state
