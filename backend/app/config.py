"""
Application configuration — environment variables with fail-fast validation.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Database
    database_url: str
    database_echo: bool = False

    # LLM Providers
    gemini_api_key: str
    groq_api_key: str
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.1-8b-instant"
    gemini_timeout_seconds: float = 1.8
    groq_timeout_seconds: float = 1.8

    # Cache
    redis_url: str

    # CORS
    frontend_origin: str

    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "info"

    # Session store
    session_store_backend: str = "redis"  # "memory" or "redis"
    session_ttl_hours: int = 6

    # Cache settings
    product_cache_ttl_minutes: int = 30
    product_cache_refresh_interval_minutes: int = 20
    query_cache_ttl_hours: int = 24

    # Rate limiting
    rate_limit_session_message_per_min: int = 20
    rate_limit_general_per_min: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore unknown fields

    def validate_required_secrets(self) -> None:
        """Fail fast if critical secrets are missing."""
        required = [
            "database_url",
            "gemini_api_key",
            "groq_api_key",
            "redis_url",
            "frontend_origin",
        ]
        missing = [key for key in required if not getattr(self, key)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()  # type: ignore
    settings.validate_required_secrets()
    return settings
