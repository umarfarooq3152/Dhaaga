from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest

from app.schemas.session import IntentExtractionResult, SessionState
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


@pytest.mark.asyncio
async def test_knitted_brown_polos_are_searched_without_inventing_formal_style():
    store = MemorySessionStore()
    provider = AsyncMock()
    provider.extract.return_value = IntentExtractionResult(
        color_preference="brown",
        category="polo",
        style_descriptors=["knitted"],
        operation="new_search",
        semantic_query="men's knitted brown polo",
        assistant_reply="",
    )
    query_cache_repo = AsyncMock()
    query_cache_repo.get_cached.return_value = None
    brand_repo = AsyncMock()
    brand_repo.get_all_active.return_value = [
        SimpleNamespace(slug="men-brand", domain="men.example", department="men")
    ]
    cache_service = AsyncMock()
    cache_service.get_or_refresh.return_value = [
        Product(
            id="men-brand:1",
            name="Knitted Polo",
            category="Polo",
            colors=["Brown"],
            department="men",
            price=3500,
            image="https://example.com/polo.jpg",
            product_url="https://example.com/polo",
        )
    ]
    service = SessionService(
        session_store=store,
        fallback_provider=provider,
        chat_repo=AsyncMock(),
        events_repo=AsyncMock(),
        query_cache_repo=query_cache_repo,
        brand_repo=brand_repo,
        cache_service=cache_service,
    )

    response = await service.handle_turn(
        "polo-session", None, "knitted brown polos", department="men"
    )

    assert response.session_state.category == "polo"
    assert response.session_state.style_descriptors == ["knitted"]
    assert response.filters["category"] == "Polo"
    assert response.filters["style"] == "Knitted"
    assert [product.id for product in response.products.items] == ["men-brand:1"]
    assert response.reply.strip()


@pytest.mark.asyncio
async def test_empty_provider_clarification_never_creates_a_blank_reply():
    store = MemorySessionStore()
    service = _service(store)
    service._query_cache_repo.get_cached.return_value = None
    service._fallback_provider.extract.return_value = IntentExtractionResult(
        assistant_reply="",
        clarify=True,
    )

    response = await service.handle_turn("blank-reply", None, "hello")

    assert response.reply.strip()


def _catalog_backed_service(
    store: MemorySessionStore,
    products: list[Product],
    provider_results: list[IntentExtractionResult],
    department: str = "men",
) -> SessionService:
    provider = AsyncMock()
    provider.extract.side_effect = provider_results
    query_cache_repo = AsyncMock()
    query_cache_repo.get_cached.return_value = None
    brand_repo = AsyncMock()
    brand_repo.get_all_active.return_value = [
        SimpleNamespace(slug="test-brand", domain="test.example", department=department)
    ]
    cache_service = AsyncMock()
    cache_service.get_or_refresh.return_value = products
    return SessionService(
        session_store=store,
        fallback_provider=provider,
        chat_repo=AsyncMock(),
        events_repo=AsyncMock(),
        query_cache_repo=query_cache_repo,
        brand_repo=brand_repo,
        cache_service=cache_service,
    )


@pytest.mark.asyncio
async def test_a_bare_garment_search_shows_products_without_an_extra_gate_turn():
    sweater = Product(
        id="test-brand:1", name="Crew Neck Knit", category="KNITWEAR",
        department="men", price=3500, image="https://example.com/s.jpg",
        product_url="https://example.com/s",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [sweater],
        [IntentExtractionResult(
            category="sweater", operation="new_search",
            semantic_query="men's sweater", assistant_reply="Here are sweaters."
        )],
    )

    response = await service.handle_turn("bare-sweater", None, "sweater", department="men")

    assert response.session_state.category == "sweater"
    assert response.products.items == [sweater]


@pytest.mark.asyncio
async def test_llm_interpreted_messy_womens_mehndi_request_returns_event_apparel():
    sharara = Product(
        id="test-brand:1", name="Green Mirror Work Sharara", category="Sharara",
        occasion="mehndi", colors=["Green"], shopify_tags=["Festive"],
        department="women", price=12000, image="https://example.com/s.jpg",
        product_url="https://example.com/s",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [sharara],
        [IntentExtractionResult(
            occasion="mehndi",
            department="women",
            style_descriptors=["female"],
            assistant_reply="",
        )],
        department="women",
    )

    response = await service.handle_turn(
        "mehndi-women", None, "mehnndi female cloths", department="men"
    )

    assert response.session_state.occasion == "mehndi"
    assert response.session_state.department == "women"
    assert response.session_state.style_descriptors == []
    assert response.products.items == [sharara]


@pytest.mark.asyncio
async def test_stale_audience_style_is_removed_from_existing_session():
    store = MemorySessionStore()
    await store.set(
        "stale-female-style",
        SessionState(
            occasion="mehndi", department="women", style_descriptors=["female"]
        ),
    )

    response = await _service(store).handle_turn(
        "stale-female-style", None, "remove occasion"
    )

    assert response.session_state.occasion is None
    assert response.session_state.style_descriptors == []


@pytest.mark.asyncio
async def test_standalone_category_change_drops_old_color_and_product_topic():
    jacket = Product(
        id="test-brand:1", name="Black Winter Jacket", category="Jackets",
        colors=["Black"], department="men", price=7000,
        image="https://example.com/j.jpg", product_url="https://example.com/j",
    )
    belt = Product(
        id="test-brand:2", name="Leather Belt", category="Belts",
        colors=["Brown"], department="men", price=2500,
        image="https://example.com/b.jpg", product_url="https://example.com/b",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [jacket, belt],
        [
            IntentExtractionResult(
                category="jacket", color_preference="black",
                style_descriptors=["winter"], operation="new_search",
                semantic_query="men's black winter jacket", assistant_reply="",
            ),
            IntentExtractionResult(
                category="belt", operation="new_search",
                semantic_query="men's belts", assistant_reply="",
            ),
        ],
    )

    first = await service.handle_turn(
        "topic-switch", None, "winter jacket black", department="men"
    )
    second = await service.handle_turn("topic-switch", None, "belts")

    assert first.session_state.category == "jacket"
    assert first.session_state.color_preference == "black"
    assert second.session_state.category == "belt"
    assert second.session_state.color_preference is None
    assert second.session_state.style_descriptors == []
    assert second.products.items == [belt]


@pytest.mark.asyncio
async def test_standalone_knitted_polo_search_drops_old_baraat_tracksuit_context():
    waistcoat = Product(
        id="test-brand:1", name="Blue Formal Waistcoat", category="Waistcoat",
        colors=["Blue"], occasion="baraat", department="men", price=9000,
        image="https://example.com/w.jpg", product_url="https://example.com/w",
    )
    polo = Product(
        id="test-brand:2", name="Knitted Polo", category="Polo",
        tags=["knitted"], department="men", price=2500,
        image="https://example.com/p.jpg", product_url="https://example.com/p",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [waistcoat, polo],
        [
            IntentExtractionResult(
                occasion="baraat", category="tracksuit",
                color_preference="blue", operation="new_search",
                semantic_query="blue men's tracksuit for baraat",
                assistant_reply="",
            ),
            IntentExtractionResult(
                category="polo", style_descriptors=["knitted"],
                budget_max=3000, operation="new_search",
                semantic_query="men's knitted polo under 3000",
                assistant_reply="",
            ),
        ],
        department="men",
    )

    first = await service.handle_turn(
        "polo-topic-switch", None, "blue tracksuit for baraat", department="men"
    )
    second = await service.handle_turn(
        "polo-topic-switch", None, "show knitted polos for me less than 3000"
    )

    assert first.session_state.category == "tracksuit"
    assert first.session_state.occasion == "baraat"
    assert second.session_state.category == "polo"
    assert second.session_state.occasion is None
    assert second.session_state.color_preference is None
    assert second.session_state.style_descriptors == ["knitted"]
    assert second.session_state.budget_max == 3000
    assert second.products.items == [polo]


@pytest.mark.asyncio
async def test_adult_product_request_leaves_a_previous_juniors_topic():
    kids = Product(
        id="test-brand:1", name="Junior Baggy Jeans", category="Jeans",
        department="men", is_kids=True, price=2500,
        image="https://example.com/k.jpg", product_url="https://example.com/k",
    )
    adult = Product(
        id="test-brand:2", name="Dark Blue Baggy Jeans", category="Jeans",
        colors=["Dark Blue"], department="men", price=4500,
        image="https://example.com/a.jpg", product_url="https://example.com/a",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [kids, adult],
        [
            IntentExtractionResult(
                wants_kids=True, operation="new_search",
                semantic_query="boys' junior clothing", assistant_reply="",
            ),
            IntentExtractionResult(
                category="jeans", color_preference="dark blue",
                style_descriptors=["baggy"], wants_kids=False,
                operation="new_search", semantic_query="men's dark blue baggy jeans",
                assistant_reply="",
            ),
        ],
    )

    kids_response = await service.handle_turn(
        "kids-to-adult", None, "juniors cloths", department="men"
    )
    adult_response = await service.handle_turn(
        "kids-to-adult", None,
        "dark blue baggy jeans I can wear with a black shirt",
    )

    assert kids_response.session_state.wants_kids is True
    assert kids_response.products.items == [kids]
    assert adult_response.session_state.wants_kids is False
    assert adult_response.session_state.category == "jeans"
    assert adult_response.session_state.style_descriptors == ["baggy"]
    assert adult_response.products.items == [adult]


@pytest.mark.asyncio
async def test_product_followup_preserves_child_age_until_explicit_adult_switch():
    store = MemorySessionStore()
    await store.set(
        "daughter-search",
        SessionState(
            occasion="mehndi",
            department="women",
            wants_kids=True,
            child_age_months=24,
            hard_constraints=["occasion", "child_age_months"],
        ),
    )
    child = Product(
        id="test-brand:kid",
        name="Green Kids Shirt",
        category="Shirt",
        colors=["Green"],
        department="women",
        is_kids=True,
        age_ranges_months=[(24, 47)],
        price=2500,
        image="https://example.com/kid.jpg",
        product_url="https://example.com/kid",
    )
    adult = Product(
        id="test-brand:adult",
        name="Green Women's Shirt",
        category="Shirt",
        colors=["Green"],
        department="women",
        price=4500,
        image="https://example.com/adult.jpg",
        product_url="https://example.com/adult",
    )
    service = _catalog_backed_service(
        store,
        [adult, child],
        [IntentExtractionResult(
            category="shirt",
            color_preference="green",
            operation="new_search",
            semantic_query="green shirt",
            assistant_reply="I found women's green shirts.",
        )],
        department="unisex",
    )

    response = await service.handle_turn(
        "daughter-search", None, "show green shirts"
    )

    assert response.session_state.wants_kids is True
    assert response.session_state.child_age_months == 24
    assert "child_age_months" in response.session_state.hard_constraints
    assert response.products.items == [child]
    assert "kids' for age 2 years" in response.reply
    assert "women's" not in response.reply


@pytest.mark.asyncio
async def test_child_gender_switch_preserves_kids_mode_and_exact_age():
    store = MemorySessionStore()
    await store.set("son-search", SessionState(department="women"))
    boy = Product(
        id="test-brand:boy", name="Toddler Boy Kurta", category="Kurta",
        department="men", is_kids=True, age_ranges_months=[(24, 47)],
        price=2500, image="https://example.com/boy.jpg",
        product_url="https://example.com/boy",
    )
    girl = Product(
        id="test-brand:girl", name="Toddler Girl Kurta", category="Kurta",
        department="women", is_kids=True, age_ranges_months=[(24, 47)],
        price=2500, image="https://example.com/girl.jpg",
        product_url="https://example.com/girl",
    )
    service = _catalog_backed_service(
        store,
        [girl, boy],
        [IntentExtractionResult(assistant_reply="")],
        department="unisex",
    )

    response = await service.handle_turn(
        "son-search", None, "kurta for my 2 year old son"
    )

    assert response.session_state.department == "men"
    assert response.session_state.wants_kids is True
    assert response.session_state.child_age_months == 24
    assert response.products.items == [boy]


@pytest.mark.asyncio
async def test_daaku_costume_request_uses_a_relevant_kurta_fallback():
    kurta = Product(
        id="test-brand:1", name="Textured Brown Kurta", category="Kurta",
        department="men", price=4500, image="https://example.com/d.jpg",
        product_url="https://example.com/d",
    )
    shirt = Product(
        id="test-brand:2", name="Basic White Shirt", category="Shirt",
        department="men", price=2500, image="https://example.com/s.jpg",
        product_url="https://example.com/s",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [shirt, kurta],
        [IntentExtractionResult(
            category="kurta",
            operation="new_search", semantic_query="men's rugged brown kurta costume",
            assistant_reply="",
        )],
    )

    response = await service.handle_turn(
        "daaku-look", None, "dress up like a bandit for daaku day", department="men"
    )

    assert response.session_state.category == "kurta"
    assert response.products.items == [kurta]


@pytest.mark.asyncio
async def test_generic_formal_event_refines_results_without_exact_occasion_dead_end():
    formal = Product(
        id="test-brand:1", name="Pink Striped Oxford Shirt", category="Shirt",
        colors=["Pink"], shopify_tags=["Formal"], department="men", price=5000,
        image="https://example.com/formal.jpg", product_url="https://example.com/formal",
    )
    casual = Product(
        id="test-brand:2", name="Pink Striped T-Shirt", category="T-Shirts",
        colors=["Pink"], department="men", price=2500,
        image="https://example.com/casual.jpg", product_url="https://example.com/casual",
    )
    provider = IntentExtractionResult(
        style_descriptors=["formal"],
        operation="refine",
        semantic_query="men's formal pink striped shirt",
        assistant_reply="What is your budget?",
    )
    service = _catalog_backed_service(
        MemorySessionStore(), [casual, formal], [
            IntentExtractionResult(
                category="shirt", color_preference="pink",
                style_descriptors=["striped"], operation="new_search",
                semantic_query="men's pink striped shirt", assistant_reply="",
            ),
            provider,
        ]
    )

    first = await service.handle_turn(
        "formal-refinement", None, "pink stripes shirt", department="men"
    )
    second = await service.handle_turn(
        "formal-refinement", None, "for a formal event"
    )
    third = await service.handle_turn(
        "formal-refinement", None, "without striped"
    )

    assert first.session_state.style_descriptors == ["striped"]
    assert second.session_state.occasion is None
    assert second.session_state.style_descriptors == ["striped", "formal"]
    assert second.products.items == [formal]
    assert "budget?" not in second.reply.lower()
    assert third.session_state.style_descriptors == ["formal"]
    assert third.session_state.category == "shirt"
    assert third.session_state.color_preference == "pink"
    assert third.products.items == [formal]


@pytest.mark.asyncio
async def test_standalone_event_request_does_not_keep_the_previous_product_category():
    jacket = Product(
        id="test-brand:1", name="Black Winter Jacket", category="Jacket",
        colors=["Black"], department="women", price=7000,
        image="https://example.com/j.jpg", product_url="https://example.com/j",
    )
    sharara = Product(
        id="test-brand:2", name="Yellow Mirror Work Sharara", category="Sharara",
        colors=["Yellow"], shopify_tags=["Embroidered", "Festive"],
        department="women", price=12000, image="https://example.com/m.jpg",
        product_url="https://example.com/m",
    )
    service = _catalog_backed_service(
        MemorySessionStore(),
        [jacket, sharara],
        [
            IntentExtractionResult(
                category="jacket", color_preference="black",
                style_descriptors=["winter"], operation="new_search",
                semantic_query="women's black winter jacket", assistant_reply="",
            ),
            IntentExtractionResult(
                occasion="mehndi", operation="new_search",
                semantic_query="women's clothing for cousin's mehndi", assistant_reply="",
            ),
        ],
        department="women",
    )

    await service.handle_turn(
        "event-switch", None, "black winter jacket", department="women"
    )
    response = await service.handle_turn("event-switch", None, "cousin's mehndi")

    assert response.session_state.category is None
    assert response.session_state.color_preference is None
    assert response.session_state.occasion == "mehndi"
    assert response.products.items == [sharara]
