import json
import re
from typing import Any


def _preprocess_llm_json(data: dict[str, Any]) -> dict[str, Any]:
    """
    Pre-process LLM output to fix common formatting issues before Pydantic validation.
    
    Handles:
    - Unwrapping nested response objects (e.g., {'SalesIntelligenceOutput': {...}})
    - Flattening speaker fields that come as dicts instead of strings
    - Fixing null values and missing required fields
    """
    if not isinstance(data, dict):
        return data
    
    # Handle wrapper objects (LLM sometimes wraps output)
    if len(data) == 1:
        key = list(data.keys())[0]
        if key == "SalesIntelligenceOutput" and isinstance(data[key], dict):
            data = data[key]
        elif key in ["analysis", "response", "output"] and isinstance(data[key], dict):
            inner = data[key]
            if "sales_speaker" in inner or "client_speaker" in inner or "summary" in inner:
                data = inner
    
    # Flatten speaker fields if they come as dicts
    if isinstance(data.get("sales_speaker"), dict):
        speaker_dict = data["sales_speaker"]
        if "name" in speaker_dict:
            data["sales_speaker"] = speaker_dict["name"]
        elif "role" in speaker_dict:
            data["sales_speaker"] = speaker_dict["role"]
        else:
            data["sales_speaker"] = str(speaker_dict)
    
    if isinstance(data.get("client_speaker"), dict):
        speaker_dict = data["client_speaker"]
        if "name" in speaker_dict:
            data["client_speaker"] = speaker_dict["name"]
        elif "role" in speaker_dict:
            data["client_speaker"] = speaker_dict["role"]
        else:
            data["client_speaker"] = str(speaker_dict)
    
    # Ensure required string/enum fields are strings, not None
    if data.get("sentiment_assessment") is None:
        data["sentiment_assessment"] = {}
    if data.get("lead_stage_assessment") is None:
        data["lead_stage_assessment"] = {}
    if data.get("urgency_level") is None:
        data["urgency_level"] = "Medium"
    if data.get("summary") is None:
        data["summary"] = ""
    if data.get("confidence_score") is None:
        data["confidence_score"] = 50
    
    return data


def parse_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty LLM response")

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _preprocess_llm_json(parsed)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        try:
            parsed = json.loads(fenced.group(1))
            if isinstance(parsed, dict):
                return _preprocess_llm_json(parsed)
        except json.JSONDecodeError:
            pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, dict):
                return _preprocess_llm_json(parsed)
        except json.JSONDecodeError:
            pass

    import logging
    logger = logging.getLogger("ai_closer.parser")
    logger.error("Failed to parse JSON. Raw LLM output: %s", raw[:500])
    raise ValueError("LLM response did not contain a JSON object")
