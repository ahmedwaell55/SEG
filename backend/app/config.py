from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Closer"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "sqlite:///./ai_closer.db"

    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000,null"

    llm_provider: str = Field(default="ollama", description="ollama, groq, or mock")
    llm_model: str = "llama3.1:8b"
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = Field(
        default=0.3,
        description="Temperature for LLM generation. Production: 0.2-0.4 for deterministic, grounded outputs."
    )
    llm_timeout_seconds: int | None = 600
    fallback_to_mock_on_llm_error: bool = True
    max_transcript_chunk_chars: int = 12000
    max_prompt_chars: int = 18000
    
    # Services catalog (JSON — single source of truth for pricing)
    services_catalog_path: str = "data/services.json"

    # Anti-hallucination settings
    require_transcript_evidence: bool = Field(
        default=True,
        description="Enforce all outputs must cite transcript evidence."
    )
    forbid_speculative_language: bool = Field(
        default=True,
        description="Forbid speculative terms ('likely', 'probably', 'might') in grounded analysis."
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("llm_temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Enforce production-safe temperature range for grounded outputs."""
        if v < 0.2 or v > 0.4:
            import logging
            logger = logging.getLogger("ai_closer.config")
            logger.warning(
                f"llm_temperature={v} outside recommended range [0.2, 0.4]. "
                "Low temperature produces more deterministic, grounded outputs. "
                "Consider setting to 0.3 for production."
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
