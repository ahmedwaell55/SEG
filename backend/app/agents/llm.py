import json
import logging
from app.agents.json_preprocessor import preprocess_llm_json, flatten_nested_fields
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.agents.parser import parse_json_object
from app.config import get_settings

logger = logging.getLogger("ai_closer.llm")


class LLMServiceError(RuntimeError):
    pass


class BaseLLMProvider:
    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        raise NotImplementedError


class OllamaProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        # Full analysis and follow-up batches need more tokens
        is_full_analysis = "acceptance_probability" in system_prompt or "lead_stage" in system_prompt
        is_followup = "followups" in system_prompt or "متابعة" in system_prompt
        if is_full_analysis:
            num_predict = 1800
        elif is_followup:
            num_predict = 2800
        else:
            num_predict = 400

        payload = {
            "model": self.settings.llm_model,
            "prompt": f"{system_prompt}\n\n{user_prompt}",
            "format": "json",
            "stream": False,
            "options": {
                "temperature": self.settings.llm_temperature,
                "num_predict": num_predict,
                "num_ctx": 6144 if is_full_analysis else 3072,  # Give a bit more context space for comprehensive prompt
                "repeat_penalty": 1.1,
            },
        }
        timeout = self.settings.llm_timeout_seconds
        if timeout is not None and timeout <= 0:
            timeout = None
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        return parse_json_object(str(data.get("response", "")))


class GroqProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.groq_api_key:
            raise LLMServiceError("GROQ_API_KEY is required when LLM_PROVIDER=groq")

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.llm_temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        timeout = self.settings.llm_timeout_seconds
        if timeout is not None and timeout <= 0:
            timeout = None
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return parse_json_object(content)


class MockProvider(BaseLLMProvider):
    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:  # noqa: ARG002
        raise LLMServiceError("MockProvider requires task-specific fallback data.")


def build_provider() -> BaseLLMProvider:
    provider = get_settings().llm_provider.lower().strip()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "groq":
        return GroqProvider()
    if provider == "mock":
        return MockProvider()
    raise LLMServiceError(f"Unsupported LLM_PROVIDER: {provider}")


async def generate_agent_json(
    system_prompt: str,
    user_prompt: str,
    fallback: dict[str, Any],
    pydantic_model: type[BaseModel] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.llm_provider.lower().strip() == "mock":
        return fallback

    provider = build_provider()
    current_user_prompt = user_prompt
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            # 1. Generate Raw JSON response
            raw_response = await provider.generate_json(system_prompt, current_user_prompt)
            
            # 1b. Preprocess to fix common LLM JSON issues
            response = preprocess_llm_json(json.dumps(raw_response))
            response = flatten_nested_fields(response)
            
            # 2. Perform Pydantic Validation if schema is provided
            if pydantic_model is not None:
                validated_model = pydantic_model.model_validate(response)
                # Return the validated dict
                return validated_model.model_dump()
            
            return response

        except (ValueError, ValidationError, json.JSONDecodeError, httpx.HTTPError) as exc:
            logger.warning(
                "LLM generate attempt %d failed. Error: %s. Provider: %s",
                attempt,
                str(exc),
                settings.llm_provider,
            )
            # Log the actual response for debugging
            if hasattr(exc, '__context__') and exc.__context__:
                logger.debug(f"Response context: {str(exc.__context__)[:200]}")
            if attempt == max_retries:
                if settings.fallback_to_mock_on_llm_error:
                    logger.error("LLM processing fully failed. Returning fallback data structure.")
                    return fallback
                raise LLMServiceError(f"Failed after {max_retries} attempts. Original error: {exc}") from exc

            # Error feedback loops: supply the exception detail back to the LLM to self-correct
            error_details = str(exc)
            current_user_prompt = (
                f"{user_prompt}\n\n"
                f"CRITICAL ERROR (Attempt {attempt} of {max_retries}):\n"
                f"Your previous output failed validation/parsing with the following error:\n"
                f"--- \n{error_details}\n ---\n"
                f"Please correct the JSON formatting and missing/invalid keys. Ensure EVERY schema field is populated correctly."
            )
