"""Tests for Gemini-primary/Groq-fallback orchestration."""

import asyncio

import pytest

from app.errors import ExternalServiceError
from app.llm.fallback import FallbackIntentProvider
from app.schemas.session import IntentExtractionResult, SessionState


class FakeProvider:
    """Configurable fake provider for testing fallback behavior."""

    def __init__(self, *, result=None, error=None, delay=0.0):
        self._result = result
        self._error = error
        self._delay = delay
        self.call_count = 0

    async def extract(self, text: str, context: SessionState) -> IntentExtractionResult:
        self.call_count += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        return self._result


def _result(reply="ok") -> IntentExtractionResult:
    return IntentExtractionResult(assistant_reply=reply)


@pytest.mark.asyncio
async def test_primary_success_never_calls_fallback():
    primary = FakeProvider(result=_result("from primary"))
    fallback = FakeProvider(result=_result("from fallback"))
    provider = FallbackIntentProvider(primary, fallback, 1.0, 1.0)

    result = await provider.extract("hi", SessionState())

    assert result.assistant_reply == "from primary"
    assert fallback.call_count == 0


@pytest.mark.asyncio
async def test_primary_timeout_falls_back_to_secondary():
    primary = FakeProvider(result=_result("from primary"), delay=0.3)
    fallback = FakeProvider(result=_result("from fallback"))
    provider = FallbackIntentProvider(primary, fallback, primary_timeout_seconds=0.05, fallback_timeout_seconds=1.0)

    result = await provider.extract("hi", SessionState())

    assert result.assistant_reply == "from fallback"
    assert fallback.call_count == 1


@pytest.mark.asyncio
async def test_primary_provider_error_falls_back_to_secondary():
    primary = FakeProvider(error=ExternalServiceError("boom", service="gemini"))
    fallback = FakeProvider(result=_result("from fallback"))
    provider = FallbackIntentProvider(primary, fallback, 1.0, 1.0)

    result = await provider.extract("hi", SessionState())

    assert result.assistant_reply == "from fallback"


@pytest.mark.asyncio
async def test_both_providers_failing_raises_external_service_error():
    primary = FakeProvider(error=ExternalServiceError("primary down", service="gemini"))
    fallback = FakeProvider(error=ExternalServiceError("fallback down", service="groq"))
    provider = FallbackIntentProvider(primary, fallback, 1.0, 1.0)

    with pytest.raises(ExternalServiceError):
        await provider.extract("hi", SessionState())


@pytest.mark.asyncio
async def test_fallback_timeout_also_raises_external_service_error():
    primary = FakeProvider(error=ExternalServiceError("primary down", service="gemini"))
    fallback = FakeProvider(result=_result("too slow"), delay=0.3)
    provider = FallbackIntentProvider(primary, fallback, primary_timeout_seconds=1.0, fallback_timeout_seconds=0.05)

    with pytest.raises(ExternalServiceError):
        await provider.extract("hi", SessionState())
