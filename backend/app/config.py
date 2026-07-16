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
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    gemini_model: str = "gemini-3.1-flash-lite"
    groq_model: str = "llama-3.1-8b-instant"
    gemini_timeout_seconds: float = 4.0
    groq_timeout_seconds: float = 6.0
    gemini_rate_limit_cooldown_seconds: float = 300.0
    llm_first_intent_enabled: bool = True

    # Cached retrieval followed by bounded live Shopify verification.
    live_product_validation_enabled: bool = True
    live_product_timeout_seconds: float = 2.0
    live_product_concurrency: int = 16
    live_product_shortlist_size: int = 32

    # Browser extension MVP
    extension_allowed_domains: str = "outfitters.com.pk,www.outfitters.com.pk"
    extension_allowed_origins: str = ""
    extension_catalog_max_products: int = 5000
    extension_catalog_cache_ttl_minutes: int = 15
    extension_request_timeout_seconds: float = 25.0
    extension_rank_candidate_limit: int = 40
    extension_result_limit: int = 40

    # Cache
    redis_url: str

    # CORS
    frontend_origin: str

    # Auth
    jwt_secret_key: str
    jwt_expiry_days: int = 30

    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "info"

    # Session store
    session_store_backend: str = "redis"  # "memory" or "redis"
    session_ttl_hours: int = 6

    # Cache settings
    product_cache_ttl_minutes: int = 1440
    product_cache_refresh_interval_minutes: int = 120
    query_cache_ttl_hours: int = 24

    # Rate limiting
    rate_limit_session_message_per_min: int = 20
    rate_limit_general_per_min: int = 60
    rate_limit_auth_per_min: int = 10  # signup/login — throttles brute-force/credential-stuffing

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
            "jwt_secret_key",
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
