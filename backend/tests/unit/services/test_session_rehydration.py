from unittest.mock import AsyncMock

import pytest

from app.schemas.session import SessionState
from app.services.session_service import SessionService
from app.session_store.memory_store import MemorySessionStore


def _service(store: MemorySessionStore) -> SessionService:
    chat_repo = AsyncMock()
    events_repo = AsyncMock()
    brand_repo = AsyncMock()
    brand_repo.get_all_active.return_value = []
    return SessionService(
        session_store=store,
        fallback_provider=AsyncMock(),
        chat_repo=chat_repo,
        events_repo=events_repo,
        query_cache_repo=AsyncMock(),
        brand_repo=brand_repo,
        cache_service=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_expired_server_session_rehydrates_last_client_context():
    store = MemorySessionStore()
    client_state = SessionState(
        occasion="mehndi", color_preference="yellow", department="women"
    )

    response = await _service(store).handle_turn(
        "expired-session", None, "show more", client_state=client_state
    )

    assert response.session_state.occasion == "mehndi"
    assert response.session_state.color_preference == "yellow"
    assert response.session_state.department == "women"


@pytest.mark.asyncio
async def test_server_state_wins_when_session_still_exists():
    store = MemorySessionStore()
    await store.set(
        "live-session",
        SessionState(occasion="mehndi", color_preference="green", department="women"),
    )
    stale_client_state = SessionState(
        occasion="mehndi", color_preference="yellow", department="women"
    )

    response = await _service(store).handle_turn(
        "live-session", None, "show more", client_state=stale_client_state
    )

    assert response.session_state.color_preference == "green"
