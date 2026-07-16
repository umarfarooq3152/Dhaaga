"""Gemini-primary / Groq-fallback orchestration for intent extraction."""

import asyncio
import logging
import time
from collections.abc import Callable

from app.errors import ExternalServiceError
from app.llm.provider import IntentExtractionProvider
from app.schemas.session import IntentExtractionResult, SessionState

logger = logging.getLogger(__name__)


class FallbackIntentProvider:
    """Tries the primary provider first; falls back to the secondary on
    timeout, rate-limit, or any other provider error.

    Rate-limit responses open a small in-process circuit so a known unavailable
    primary is skipped until its cooldown expires. Other failures continue to
    retry the primary on the next request.
    """

    def __init__(
        self,
        primary: IntentExtractionProvider,
        fallback: IntentExtractionProvider,
        primary_timeout_seconds: float,
        fallback_timeout_seconds: float,
        primary_rate_limit_cooldown_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._primary = primary
        self._fallback = fallback
        self._primary_timeout = primary_timeout_seconds
        self._fallback_timeout = fallback_timeout_seconds
        self._primary_rate_limit_cooldown = max(
            0.0, primary_rate_limit_cooldown_seconds
        )
        self._clock = clock
        self._primary_unavailable_until = 0.0

    @staticmethod
    def _is_rate_limit_error(error: ExternalServiceError) -> bool:
        return (
            error.details.get("status_code") == 429
            or error.details.get("reason") == "rate_limited"
        )

    async def _extract_fallback(
        self, text: str, context: SessionState
    ) -> IntentExtractionResult:
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

    async def extract(
        self, text: str, context: SessionState
    ) -> IntentExtractionResult:
        now = self._clock()
        if now < self._primary_unavailable_until:
            logger.info(
                "Skipping rate-limited primary LLM provider for another %.1fs",
                self._primary_unavailable_until - now,
            )
            return await self._extract_fallback(text, context)

        try:
            result = await asyncio.wait_for(
                self._primary.extract(text, context),
                timeout=self._primary_timeout,
            )
            self._primary_unavailable_until = 0.0
            return result
        except (TimeoutError, ExternalServiceError) as primary_error:
            logger.warning(
                f"Primary LLM provider failed/timed out, falling back to secondary: {primary_error}"
            )
            if (
                isinstance(primary_error, ExternalServiceError)
                and self._is_rate_limit_error(primary_error)
            ):
                self._primary_unavailable_until = (
                    self._clock() + self._primary_rate_limit_cooldown
                )
                logger.warning(
                    "Primary LLM rate limit circuit opened for %.1fs",
                    self._primary_rate_limit_cooldown,
                )

        return await self._extract_fallback(text, context)
