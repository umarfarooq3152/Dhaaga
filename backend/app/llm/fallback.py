"""Gemini-primary / Groq-fallback orchestration for intent extraction."""

import asyncio
import logging

from app.errors import ExternalServiceError
from app.llm.provider import IntentExtractionProvider
from app.schemas.session import IntentExtractionResult, SessionState

logger = logging.getLogger(__name__)


class FallbackIntentProvider:
    """Tries the primary provider first; falls back to the secondary on
    timeout, rate-limit, or any other provider error.

    Worst-case latency is roughly primary_timeout + fallback_timeout — this
    is an accepted, rare-path trade-off (most turns hit the fast-path
    classifier or query cache and never reach an LLM call at all).
    """

    def __init__(
        self,
        primary: IntentExtractionProvider,
        fallback: IntentExtractionProvider,
        primary_timeout_seconds: float,
        fallback_timeout_seconds: float,
    ):
        self._primary = primary
        self._fallback = fallback
        self._primary_timeout = primary_timeout_seconds
        self._fallback_timeout = fallback_timeout_seconds

    async def extract(
        self, text: str, context: SessionState
    ) -> IntentExtractionResult:
        try:
            return await asyncio.wait_for(
                self._primary.extract(text, context),
                timeout=self._primary_timeout,
            )
        except (TimeoutError, ExternalServiceError) as primary_error:
            logger.warning(
                f"Primary LLM provider failed/timed out, falling back to secondary: {primary_error}"
            )

        try:
            return await asyncio.wait_for(
                self._fallback.extract(text, context),
                timeout=self._fallback_timeout,
            )
        except (TimeoutError, ExternalServiceError) as fallback_error:
            logger.error(f"Fallback LLM provider also failed: {fallback_error}")
            raise ExternalServiceError(
                "Both primary and fallback LLM providers failed",
                service="llm_fallback",
            ) from fallback_error
