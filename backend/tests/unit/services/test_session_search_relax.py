"""Tests for the filter-relaxation cascade in session_service.py.

Regression coverage for a real bug found via live testing: asking for
"pink wedding wear" replied "Updated to pink — here's what matches" while
the shown grid was red/purple/grey/gold/green — the color filter had
been silently dropped by a relaxation step that unconditionally replaced
the result with a fully-unfiltered search any time color/size were merely
*set*, regardless of whether an occasion+budget-relaxed (but still
color-filtered) result had already cleared the results threshold.
"""

from app.schemas.product import Product
from app.schemas.session import SessionState
from app.services.session_service import (
    MIN_RESULTS_BEFORE_RELAX,
    _build_filters,
    _relaxation_notice,
    _search_with_relax,
)


def _product(brand: str, external_id: str, name: str, price: float, color: str, occasion: str) -> Product:
    return Product(
        id=f"{brand}:{external_id}",
        name=name,
        description="",
        price=price,
        colors=[color],
        sizes=["M"],
        occasion=occasion,
        category=None,
        tags=[],
        shopify_tags=[],
        image="https://example.com/1.jpg",
        secondaryImage=None,
        product_url="https://example.com/products/1",
    )


def _wedding_catalog(pink_count: int, other_count: int) -> list[Product]:
    products = [
        _product("brand-a", f"pink-{i}", f"Wedding Lehenga Pink {i}", 5000, "Pink", "wedding")
        .model_copy(update={"category": "Lehenga"})
        for i in range(pink_count)
    ]
    products += [
        _product("brand-b", f"other-{i}", f"Wedding Lehenga {i}", 5000, "Red", "wedding")
        .model_copy(update={"category": "Lehenga"})
        for i in range(other_count)
    ]
    return products


def test_keeps_color_filter_when_enough_matches_exist():
    # Plenty of pink wedding matches — no relaxation should be needed at all.
    products = _wedding_catalog(pink_count=MIN_RESULTS_BEFORE_RELAX, other_count=50)
    state = SessionState(occasion="wedding", color_preference="pink", style_descriptors=[])

    relaxed = _search_with_relax(products, state, page_size=20)

    assert relaxed.effective_color == "pink"
    assert not relaxed.dropped_color
    assert all(p.colors == ["Pink"] for p in relaxed.result.items)


def test_sparse_compound_match_keeps_exact_event_items_first_then_widens():
    # Only 2 pink wedding items, but plenty of pink items overall once
    # occasion is relaxed — occasion should be dropped, color kept.
    wedding_pink = _wedding_catalog(pink_count=2, other_count=0)
    casual_pink = [
        _product("brand-c", f"casual-pink-{i}", f"Casual Pink Top {i}", 2000, "Pink", "casual")
        for i in range(MIN_RESULTS_BEFORE_RELAX)
    ]
    products = wedding_pink + casual_pink
    state = SessionState(occasion="wedding", color_preference="pink", style_descriptors=[])

    relaxed = _search_with_relax(products, state, page_size=20)

    assert relaxed.dropped_occasion
    assert relaxed.effective_color == "pink"
    assert not relaxed.dropped_color
    assert relaxed.exact_count == 2
    assert relaxed.result.total == 12
    assert all(product.occasion == "wedding" for product in relaxed.result.items[:2])
    assert all(p.colors == ["Pink"] for p in relaxed.result.items)


def test_never_drops_color_to_fill_the_grid():
    # Too few matches even after relaxing occasion — color must finally
    # be dropped too, and the reply must honestly say so (real bug: it
    # used to silently drop color while the LLM's reply still claimed
    # "updated to pink").
    products = _wedding_catalog(pink_count=1, other_count=MIN_RESULTS_BEFORE_RELAX)
    state = SessionState(occasion="wedding", color_preference="pink", style_descriptors=[])

    relaxed = _search_with_relax(products, state, page_size=20)

    assert not relaxed.dropped_occasion
    assert not relaxed.dropped_color
    assert relaxed.effective_color == "pink"
    assert relaxed.result.total == 1

    notice = _relaxation_notice(relaxed, state)
    assert notice is None


def test_budget_is_a_hard_constraint_even_for_a_sparse_result():
    products = _wedding_catalog(pink_count=2, other_count=20)
    products[0].price = 4000
    products[1].price = 9000
    state = SessionState(occasion="wedding", color_preference="pink", budget_max=5000)

    relaxed = _search_with_relax(products, state, page_size=20)

    assert not relaxed.dropped_budget
    assert [product.price for product in relaxed.result.items] == [4000]


def test_build_filters_reflects_effective_color_not_requested_color():
    state = SessionState(occasion="wedding", color_preference="pink", style_descriptors=[])

    # Color was actually honored.
    filters_kept = _build_filters(state, effective_color="pink", effective_size=None)
    assert filters_kept["color"] == "Pink"

    # Color had to be dropped — chip must not claim it's still applied.
    filters_dropped = _build_filters(state, effective_color=None, effective_size=None)
    assert "color" not in filters_dropped


def test_zero_exact_color_matches_returns_empty_without_dropping_color():
    products = _wedding_catalog(pink_count=0, other_count=4)
    state = SessionState(occasion="wedding", color_preference="pink")

    relaxed = _search_with_relax(products, state, page_size=20)

    assert relaxed.result.total == 0
    assert relaxed.dropped_color is False
    assert relaxed.dropped_occasion is False
    assert relaxed.effective_color == "pink"
    assert _relaxation_notice(relaxed, state) is None


def test_zero_event_metadata_matches_show_same_garment_as_labelled_alternatives():
    lehenga = _product(
        "brand-a", "lehenga-1", "Plain Black Lehenga", 18000, "Black", "wedding"
    ).model_copy(update={"category": "Lehenga", "shopify_tags": ["Plain"], "department": "women"})
    unrelated = _product(
        "brand-b", "shirt-1", "Casual Oxford Shirt", 4000, "Blue", "casual"
    ).model_copy(update={"category": "Shirt"})
    state = SessionState(category="lehenga", occasion="mehndi", department="women")

    relaxed = _search_with_relax([unrelated, lehenga], state, page_size=20)

    assert [product.name for product in relaxed.result.items] == ["Plain Black Lehenga"]
    assert relaxed.dropped_occasion is True
    assert relaxed.effective_occasion is None
    notice = _relaxation_notice(relaxed, state)
    assert "Sorry, I couldn't find any products matching women's lehenga for mehndi." in notice
    assert "couldn't verify them specifically for mehndi" in notice


def test_sparse_exact_event_matches_are_kept_first_before_near_matches():
    exact = _product(
        "brand-a", "lehenga-1", "Mirror Work Lehenga", 18000, "Green", "mehndi"
    ).model_copy(update={"category": "Lehenga", "department": "women"})
    other_event = _product(
        "brand-b", "lehenga-2", "Reception Lehenga", 22000, "Blue", "wedding"
    ).model_copy(update={"category": "Lehenga", "department": "women"})
    state = SessionState(category="lehenga", occasion="mehndi", department="women")

    relaxed = _search_with_relax([other_event, exact], state, page_size=20)

    assert [product.name for product in relaxed.result.items] == [
        "Mirror Work Lehenga", "Reception Lehenga"
    ]
    assert relaxed.exact_count == 1
    assert relaxed.dropped_occasion is True


def test_empty_sherwani_inventory_uses_curated_menswear_near_matches():
    prince_coat = _product(
        "brand-a", "prince-1", "Black Embroidered Prince Coat", 18000, "Black", "wedding"
    ).model_copy(update={"category": "Prince Coat", "department": "men"})
    state = SessionState(
        category="sherwani",
        color_preference="black",
        department="men",
        hard_constraints=["category"],
    )

    relaxed = _search_with_relax([prince_coat], state, page_size=20)

    assert relaxed.result.total == 1
    assert relaxed.result.items[0].name == "Black Embroidered Prince Coat"
    assert relaxed.dropped_category is True


def test_missing_requested_event_garment_shows_labelled_event_alternatives():
    sharara = _product(
        "brand-a", "sharara-1", "Green Mirror Work Sharara", 16000, "Green", "mehndi"
    ).model_copy(update={"category": "Sharara", "shopify_tags": ["Mirror Work", "Festive"], "department": "women"})
    unrelated = _product(
        "brand-b", "shirt-1", "Casual Oxford Shirt", 4000, "Blue", "casual"
    ).model_copy(update={"category": "Shirt"})
    state = SessionState(category="lehenga", occasion="mehndi", department="women")

    relaxed = _search_with_relax([unrelated, sharara], state, page_size=20)

    assert [product.name for product in relaxed.result.items] == ["Green Mirror Work Sharara"]
    assert relaxed.dropped_category is True
    assert relaxed.effective_category is None
    notice = _relaxation_notice(relaxed, state)
    assert "Sorry, I couldn't find any products matching women's lehenga for mehndi." in notice
    assert "the sharara category" in notice
    assert "try these instead" in notice


def test_generic_mehndi_requires_verified_party_level_evidence():
    plain = _product(
        "brand-a", "plain", "Green Lawn Kurta", 4500, "Green", "mehndi"
    ).model_copy(update={
        "category": "Kurta", "department": "women",
        "description": "A plain everyday lawn kurta.",
    })
    heavy = _product(
        "brand-b", "heavy", "Green Mirror Work Organza Sharara", 18000,
        "Green", "mehndi",
    ).model_copy(update={
        "category": "Sharara", "department": "women",
        "description": "Festive organza with heavy embroidery and mirror work.",
        "shopify_tags": ["Party Wear", "Festive"],
    })

    result = _search_with_relax(
        [plain, heavy], SessionState(occasion="mehndi", department="women"), 20
    ).result

    assert [product.name for product in result.items] == [heavy.name]


def test_baraat_defaults_to_heavy_party_evidence():
    lawn = _product(
        "brand-a", "lawn", "Red Lawn 3 Piece", 7000, "Red", "baraat"
    ).model_copy(update={"category": "3 Piece", "department": "women"})
    zari = _product(
        "brand-b", "zari", "Maroon Zari Velvet Lehenga", 30000,
        "Maroon", "baraat",
    ).model_copy(update={
        "category": "Lehenga", "department": "women",
        "description": "Heavy zari embroidered velvet wedding wear.",
    })

    result = _search_with_relax(
        [lawn, zari], SessionState(occasion="baraat", department="women"), 20
    ).result

    assert [product.name for product in result.items] == [zari.name]


def test_simple_mehndi_allows_formal_unembellished_fabric():
    formal = _product(
        "brand-a", "formal", "Simple Silk Pishwas", 16000, "Green", "mehndi"
    ).model_copy(update={
        "category": "Pishwas", "department": "women",
        "description": "A simple tailored silk pishwas without decorative work.",
    })

    relaxed = _search_with_relax(
        [formal],
        SessionState(
            occasion="mehndi", department="women",
            style_descriptors=["simple"],
            soft_preferences=["style_descriptors"],
        ),
        20,
    )

    assert [product.name for product in relaxed.result.items] == [formal.name]


def test_without_embellishment_rejects_work_but_keeps_formal_fabric():
    embroidered = _product(
        "brand-a", "worked", "Embroidered Organza Pishwas", 18000,
        "Green", "mehndi",
    ).model_copy(update={
        "category": "Pishwas", "department": "women",
        "description": "Organza with embroidery and sequins.",
    })
    clean = _product(
        "brand-b", "clean", "Silk Pishwas", 17000, "Green", "mehndi"
    ).model_copy(update={
        "category": "Pishwas", "department": "women",
        "description": "Tailored silk occasion wear with clean construction.",
    })

    result = _search_with_relax(
        [embroidered, clean],
        SessionState(
            occasion="mehndi", department="women",
            excluded_styles=["embellished"],
        ),
        20,
    ).result

    assert [product.name for product in result.items] == [clean.name]


def test_event_alternatives_never_include_non_garment_event_merchandise():
    stencil = _product(
        "brand-a", "stencil-1", "Mehndi Henna Stencils", 500, "Green", "mehndi"
    ).model_copy(update={"category": "OTHER-ACC", "shopify_tags": ["Mehndi"]})
    sharara = _product(
        "brand-b", "sharara-1", "Yellow Festive Sharara", 14000, "Yellow", "mehndi"
    ).model_copy(update={"category": "Sharara", "shopify_tags": ["Festive"], "department": "women"})
    state = SessionState(category="lehenga", occasion="mehndi", department="women")

    relaxed = _search_with_relax([stencil, sharara], state, page_size=20)

    assert [product.name for product in relaxed.result.items] == ["Yellow Festive Sharara"]


def test_missing_mens_tracksuit_names_the_waistcoats_actually_shown():
    waistcoat = _product(
        "brand-a", "waistcoat-1", "Blue Formal Waistcoat", 9000, "Blue", "baraat"
    ).model_copy(update={"category": "Waistcoat", "department": "men"})
    state = SessionState(
        category="tracksuit",
        occasion="baraat",
        color_preference="blue",
        department="men",
    )

    relaxed = _search_with_relax([waistcoat], state, page_size=20)
    notice = _relaxation_notice(relaxed, state)

    assert [product.name for product in relaxed.result.items] == ["Blue Formal Waistcoat"]
    assert "blue men's tracksuit for baraat" in notice
    assert "the waistcoat category" in notice
    assert "try these instead" in notice
    assert "relaxed" not in notice


def test_explicitly_hard_category_and_style_remain_hard_on_a_miss():
    cardigan = _product(
        "brand-a", "1", "Knit Cardigan", 4000, "Blue", "casual"
    ).model_copy(update={"category": "Cardigan"})
    unrelated = _product(
        "brand-b", "1", "Formal Oxford Shirt", 5000, "White", "office"
    ).model_copy(update={"category": "Shirt", "shopify_tags": ["Formal"]})
    state = SessionState(
        category="cardigan",
        style_descriptors=["formal"],
        hard_constraints=["category", "style_descriptors"],
    )

    relaxed = _search_with_relax([unrelated, cardigan], state, page_size=20)

    assert relaxed.result.items == []
    assert relaxed.dropped_style is False
    assert relaxed.effective_styles == ["formal"]


def test_budget_and_size_stay_hard_even_when_soft_details_are_unavailable():
    expensive = _product(
        "brand-a", "1", "Red Wedding Dress", 9000, "Red", "wedding"
    ).model_copy(update={"category": "Dress", "sizes": ["L"]})
    state = SessionState(
        category="dress",
        occasion="wedding",
        color_preference="pink",
        budget_max=5000,
        size="M",
    )

    relaxed = _search_with_relax([expensive], state, page_size=20)

    assert relaxed.result.total == 0
    assert relaxed.dropped_budget is False
    assert relaxed.dropped_size is False


def test_jacket_collection_tag_cannot_turn_vest_or_koti_into_jacket():
    jacket = _product(
        "brand-a", "1", "Black Leather Jacket", 7000, "Black", "casual"
    ).model_copy(update={"category": "Outerwear", "shopify_tags": ["Jackets"]})
    vest = _product(
        "brand-a", "2", "Argyle Pattern Sweater Vest", 3000, "Black", "casual"
    ).model_copy(update={"category": "Knitwear", "shopify_tags": ["Jackets"]})
    koti = _product(
        "brand-b", "1", "Applique Craft Koti", 2500, "Black", "casual"
    ).model_copy(update={"category": "Koti", "shopify_tags": ["Jackets"]})
    state = SessionState(category="jacket", color_preference="black")

    result = _search_with_relax([jacket, vest, koti], state, page_size=20).result

    assert [product.name for product in result.items] == ["Black Leather Jacket"]


def test_every_explicit_style_and_material_must_match_same_product():
    exact = _product(
        "brand-a", "1", "Slim Fit Leather Trousers", 7000, "Black", "casual"
    ).model_copy(update={"category": "Trousers", "tags": ["leather", "slim"]})
    leather_only = _product(
        "brand-b", "1", "Regular Leather Trousers", 6500, "Black", "casual"
    ).model_copy(update={"category": "Trousers", "tags": ["leather"]})
    slim_only = _product(
        "brand-c", "1", "Slim Cotton Trousers", 5000, "Black", "casual"
    ).model_copy(update={"category": "Trousers", "tags": ["slim"]})
    state = SessionState(
        category="trousers",
        color_preference="black",
        style_descriptors=["slim", "leather"],
    )

    result = _search_with_relax(
        [leather_only, slim_only, exact], state, page_size=20
    ).result

    assert [product.name for product in result.items] == ["Slim Fit Leather Trousers"]


def test_collection_tags_cannot_cross_contaminate_any_product_family():
    cases = [
        ("shirt", "Oxford Shirt", "Sweater Vest"),
        ("hoodie", "Zip Hoodie", "Crew Sweatshirt"),
        ("dress", "Midi Dress", "Wide Leg Jumpsuit"),
        ("trousers", "Straight Trousers", "Running Shorts"),
        ("kurta", "Textured Kurta", "Embroidered Waistcoat"),
    ]

    for requested, correct_name, wrong_name in cases:
        correct = _product(
            "correct", requested, correct_name, 5000, "Black", "casual"
        ).model_copy(update={"category": correct_name})
        wrong = _product(
            "wrong", requested, wrong_name, 4500, "Black", "casual"
        ).model_copy(update={"category": wrong_name, "shopify_tags": [requested]})

        result = _search_with_relax(
            [wrong, correct], SessionState(category=requested), page_size=20
        ).result

        assert [product.name for product in result.items] == [correct_name]
