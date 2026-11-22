"""Configuration helpers. Secrets must be supplied through environment variables."""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "20"))
    max_concurrency: int = int(os.getenv("MAX_CONCURRENCY", "5"))
    llm_primary_provider: str = os.getenv("LLM_PRIMARY_PROVIDER", "openai")
    llm_fallback_provider: str = os.getenv("LLM_FALLBACK_PROVIDER", "anthropic")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")

settings = Settings()
