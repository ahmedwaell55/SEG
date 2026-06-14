import json
import re
from typing import Any

def preprocess_llm_json(raw_response: str) -> dict[str, Any]:
    """
    Preprocess LLM output to fix common issues before Pydantic validation.
    Handles:
    - Dict fields that should be strings
    - Enum values that don't match exactly
    - Missing quotes on enum values
    - Malformed nested structures
    """
    import json
    
    # First try normal parsing
    try:
        data = json.loads(raw_response)
        return data
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    match = re.search(r'```(?:json)?\s*({.*?})\s*```', raw_response, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Try to extract JSON object from raw text
    start = raw_response.find('{')
    end = raw_response.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(raw_response[start:end+1])
        except json.JSONDecodeError:
            pass
    
    raise ValueError(f"Cannot parse JSON from response: {raw_response[:100]}")


def fix_enum_values(data: dict, enum_mappings: dict) -> dict:
    """
    Fix enum values that might not match exactly.
    Example: "high" -> "High", "sql" -> "SQL"
    """
    for field, expected_values in enum_mappings.items():
        if field in data and isinstance(data[field], str):
            value = data[field].strip()
            # Try exact match
            if value in expected_values:
                continue
            # Try case-insensitive match
            for expected in expected_values:
                if value.lower() == expected.lower():
                    data[field] = expected
                    break
    return data


def flatten_nested_fields(data: dict) -> dict:
    """
    Flatten dict fields that should be strings (e.g., speaker names).
    """
    # If sales_speaker or client_speaker are dicts, extract first value
    if isinstance(data.get('sales_speaker'), dict):
        speaker_dict = data['sales_speaker']
        data['sales_speaker'] = next(iter(speaker_dict.values()), "Sales Representative")
    
    if isinstance(data.get('client_speaker'), dict):
        speaker_dict = data['client_speaker']
        data['client_speaker'] = next(iter(speaker_dict.values()), "Client Representative")
    
    return data
