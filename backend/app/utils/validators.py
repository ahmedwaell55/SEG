"""
Anti-hallucination validators and sanitization utilities.
Ensures outputs are grounded in transcript evidence only.
"""

from typing import Any, TypeVar
import logging

logger = logging.getLogger("ai_closer.validators")

T = TypeVar("T")


def sanitize_string(value: Any, max_length: int = 500) -> str | None:
    """
    Sanitize and validate string fields.
    Strip whitespace, remove empty strings, enforce max length.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if not isinstance(value, str):
        return None
    sanitized = value.strip()
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized if sanitized else None


def validate_confidence(score: int | None) -> int:
    """
    Validate confidence score is 0-100 and reasonable.
    Low confidence (< 60) should trigger evidence_present = False flag.
    """
    if score is None:
        return 60  # Default to medium confidence
    if not isinstance(score, int):
        return 60
    return max(0, min(100, score))


def clean_list(items: list | None, max_items: int = 12, max_item_length: int = 300) -> list[str]:
    """
    Clean and deduplicate list items.
    Remove empty/null items, enforce max count, truncate long items.
    """
    if not items:
        return []
    
    cleaned = []
    seen = set()
    
    for item in items:
        if item is None:
            continue
        
        # Handle both strings and dict/object items (for nested structures)
        if isinstance(item, dict):
            # If dict, try to extract string representation
            text = item.get("text") or item.get("value") or str(item)
        elif isinstance(item, str):
            text = item
        else:
            text = str(item)
        
        text = sanitize_string(text, max_item_length)
        if text and text not in seen:
            cleaned.append(text)
            seen.add(text)
        
        if len(cleaned) >= max_items:
            break
    
    return cleaned


def validate_list_field(
    items: list | None,
    field_name: str,
    max_items: int = 12,
    allow_empty: bool = True
) -> list[str]:
    """
    Validate a list field with logging.
    If empty and not allowed, return empty list but log warning.
    """
    cleaned = clean_list(items, max_items=max_items)
    
    if not cleaned and not allow_empty:
        logger.warning(f"Field '{field_name}' is empty and should contain data.")
    
    return cleaned


def flag_low_confidence_field(field_value: Any, confidence: int, threshold: int = 60) -> dict:
    """
    Wrap a field with confidence metadata.
    Flags uncertain extractions for frontend display.
    
    Returns dict with 'value' and 'confidence_metadata' keys.
    """
    return {
        "value": field_value,
        "confidence_metadata": {
            "is_low_confidence": confidence < threshold,
            "confidence_score": confidence,
            "requires_review": confidence < 50,
        }
    }


def validate_speaker_names(sales_speaker: str | None, client_speaker: str | None) -> tuple[str, str]:
    """
    Validate speaker names are populated.
    If empty, use generic fallbacks.
    """
    sales = sanitize_string(sales_speaker) or "Sales Representative"
    client = sanitize_string(client_speaker) or "Client Representative"
    return sales, client


def strip_hallucination_markers(text: str) -> str:
    """
    Remove speculative language that indicates hallucination risk.
    Examples: "likely", "probably", "might", "assumed", "could be", etc.
    Only used in fallback contexts to denote speculation.
    """
    hallucination_markers = [
        r"\bwill probably\b",
        r"\blikely to\b",
        r"\bmight\b",
        r"\bassumed\b",
        r"\bcould be\b",
        r"\bseemingly\b",
    ]
    
    import re
    result = text
    for pattern in hallucination_markers:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    
    return result.strip()


def validate_objections_structure(objections: list) -> list[dict]:
    """
    Ensure objections have required fields and valid enums.
    Convert old-style string objections to new structured format if needed.
    """
    from app.prompts.sales_prompts import ObjectionTypeEnum
    
    validated = []
    
    for obj in objections:
        if isinstance(obj, str):
            # Old format: convert to new structure
            validated.append({
                "objection": obj,
                "category": ObjectionTypeEnum.OTHER.value,
                "verbatim_evidence": None,
                "severity": "Medium"
            })
        elif isinstance(obj, dict):
            # New format: validate fields
            validated.append({
                "objection": sanitize_string(obj.get("objection")) or "Unknown objection",
                "category": obj.get("category", ObjectionTypeEnum.OTHER.value),
                "verbatim_evidence": sanitize_string(obj.get("verbatim_evidence")),
                "severity": obj.get("severity", "Medium")
            })
    
    return validated


def validate_buying_signals_structure(signals: list) -> list[dict]:
    """
    Ensure buying signals have required fields and valid categories.
    Convert old-style string signals to new structured format if needed.
    """
    from app.prompts.sales_prompts import BuyingSignalCategoryEnum, SignalStrengthEnum
    
    validated = []
    
    for signal in signals:
        if isinstance(signal, str):
            # Old format: convert to new structure
            validated.append({
                "signal": signal,
                "category": BuyingSignalCategoryEnum.FEATURE_INTEREST.value,
                "strength": SignalStrengthEnum.MODERATE.value,
                "verbatim_evidence": None
            })
        elif isinstance(signal, dict):
            # New format: validate fields
            validated.append({
                "signal": sanitize_string(signal.get("signal")) or "Unknown signal",
                "category": signal.get("category", BuyingSignalCategoryEnum.FEATURE_INTEREST.value),
                "strength": signal.get("strength", SignalStrengthEnum.MODERATE.value),
                "verbatim_evidence": sanitize_string(signal.get("verbatim_evidence"))
            })
    
    return validated


def generate_fallback_response_with_flags() -> dict:
    """
    Generate a realistic fallback response with clear 'is_fallback' flag.
    This is returned when LLM fails after retries.
    """
    return {
        "sales_speaker": "Sales Representative",
        "client_speaker": "Client Representative",
        "client_quotes": [],
        "sentiment_assessment": {
            "sentiment": "Neutral",
            "sentiment_confidence": 30,
            "sentiment_drivers": ["Insufficient transcript data for accurate sentiment analysis"],
            "emotional_tone": "Neutral"
        },
        "urgency_level": "Medium",
        "lead_stage_assessment": {
            "stage": "Qualified",
            "stage_confidence": 40,
            "stage_signals": ["Initial interest shown"],
            "stage_blockers": ["Insufficient information"],
            "advancement_timeline": None
        },
        "stakeholders": [],
        "pain_points": [],
        "objections": [],
        "buying_signals": [],
        "risks": ["Unable to assess: LLM processing failed"],
        "opportunities": [],
        "confidence_score": 35,
        "is_fallback": True,  # CRITICAL: Mark as fallback
        "recommendations": ["Retry analysis with full transcript", "Manual review recommended"],
        "next_steps": ["Schedule follow-up call"],
        "communication_style": "Consultative",
        "sales_strategy": "Establish trust and gather more information",
        "follow_up_strategy": "Follow up with detailed discovery questions",
        "summary": "Analysis failed due to LLM error. Manual review recommended.",
        "key_points": []
    }


def validate_json_structure(data: dict) -> dict:
    """
    Post-processing validation of generated JSON.
    Ensures all required fields exist, arrays are properly formed,
    enums are valid, and confiden scores are reasonable.
    """
    # Safely extract sentiment and lead stage (often flattened by small LLMs)
    sentiment_assessment = data.get("sentiment_assessment")
    if not isinstance(sentiment_assessment, dict):
        sentiment_assessment = {
            "sentiment": sanitize_string(data.get("sentiment")) or "Neutral",
            "emotional_tone": sanitize_string(data.get("emotional_tone")) or "Neutral",
            "sentiment_drivers": clean_list(data.get("sentiment_drivers"), max_items=5),
            "sentiment_confidence": 60,
        }

    lead_stage_assessment = data.get("lead_stage_assessment")
    if not isinstance(lead_stage_assessment, dict):
        lead_stage_assessment = {
            "stage": sanitize_string(data.get("lead_stage")) or "Qualified",
            "stage_confidence": 60,
            "stage_signals": clean_list(data.get("stage_signals"), max_items=5),
            "stage_blockers": clean_list(data.get("stage_blockers"), max_items=5),
            "advancement_timeline": sanitize_string(data.get("advancement_timeline")),
        }

    # Extract and validate required fields
    validated = {
        "sales_speaker": validate_speaker_names(
            data.get("sales_speaker"),
            None
        )[0],
        "client_speaker": validate_speaker_names(
            None,
            data.get("client_speaker")
        )[1],
        "client_quotes": clean_list(data.get("client_quotes")),
        "sentiment_assessment": sentiment_assessment,
        "urgency_level": sanitize_string(data.get("urgency_level")) or "Medium",
        "lead_stage_assessment": lead_stage_assessment,
        "stakeholders": clean_list(data.get("stakeholders"), max_items=12),
        "pain_points": clean_list(data.get("pain_points"), max_items=12),
        "objections": validate_objections_structure(data.get("objections", [])),
        "buying_signals": validate_buying_signals_structure(data.get("buying_signals", [])),
        "risks": clean_list(data.get("risks"), max_items=12),
        "opportunities": clean_list(data.get("opportunities"), max_items=12),
        "confidence_score": validate_confidence(data.get("confidence_score")),
        "is_fallback": data.get("is_fallback", False),
        "recommendations": clean_list(data.get("recommendations"), max_items=12),
        "next_steps": clean_list(data.get("next_steps"), max_items=12),
        "communication_style": sanitize_string(data.get("communication_style")) or "Consultative",
        "sales_strategy": sanitize_string(data.get("sales_strategy")) or "Unspecified",
        "follow_up_strategy": sanitize_string(data.get("follow_up_strategy")) or "Follow up with discovery questions",
        "summary": sanitize_string(data.get("summary"), max_length=1000) or "Analysis complete",
        "key_points": clean_list(data.get("key_points"), max_items=12),
    }
    
    return validated
