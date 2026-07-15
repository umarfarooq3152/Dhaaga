from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from app.schemas.session import SessionState
from app.schemas.product import Product
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


@pytest.mark.asyncio
async def test_gender_switch_clears_old_garment_and_searches_new_department():
    store = MemorySessionStore()
    await store.set(
        "switch-session",
        SessionState(
            occasion="baraat", department="women", size="M",
            style_descriptors=["formal", "lehenga"],
        ),
    )
    await store.set_last_results("switch-session", [
        Product(
            id="women-brand:1", name="Bridal Lehenga", occasion="baraat",
            department="women", price=50000, image="https://example.com/w.jpg",
            product_url="https://example.com/w",
        )
    ])
    brand_repo = AsyncMock()
    brand_repo.get_all_active.return_value = [
        SimpleNamespace(slug="men-brand", domain="men.example", department="men")
    ]
    cache_service = AsyncMock()
    cache_service.get_or_refresh.return_value = [
        Product(
            id="men-brand:1", name="Formal Sherwani", category="Sherwani",
            occasion="baraat", department="men", price=45000,
            image="https://example.com/m.jpg", product_url="https://example.com/m",
        )
    ]
    service = SessionService(
        session_store=store, fallback_provider=AsyncMock(), chat_repo=AsyncMock(),
        events_repo=AsyncMock(), query_cache_repo=AsyncMock(),
        brand_repo=brand_repo, cache_service=cache_service,
    )

    response = await service.handle_turn("switch-session", None, "men")

    assert response.session_state.department == "men"
    assert response.session_state.size is None
    assert response.session_state.style_descriptors == ["formal"]
    assert [product.id for product in response.products.items] == ["men-brand:1"]
    brand_repo.get_all_active.assert_awaited_once_with(department="men")
