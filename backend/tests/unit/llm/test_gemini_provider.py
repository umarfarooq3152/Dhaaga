"""Tests for Gemini provider error metadata."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.errors import ExternalServiceError
from app.llm.gemini_provider import GeminiIntentProvider
from app.schemas.session import SessionState


class RateLimitError(Exception):
    code = 429


@pytest.mark.asyncio
async def test_rate_limit_error_preserves_status_for_fallback_circuit():
    provider = GeminiIntentProvider.__new__(GeminiIntentProvider)
    provider._model = "test-model"
    provider._client = Mock()
    provider._client.aio.models.generate_content = AsyncMock(
        side_effect=RateLimitError("quota exhausted")
    )

    with pytest.raises(ExternalServiceError) as raised:
        await provider.extract("show me a kurta", SessionState())

    assert raised.value.details["service"] == "gemini"
    assert raised.value.details["status_code"] == 429
    assert raised.value.details["reason"] == "rate_limited"
