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
        _product("brand-a", f"pink-{i}", f"Wedding Dress Pink {i}", 5000, "Pink", "wedding")
        for i in range(pink_count)
    ]
    products += [
        _product("brand-b", f"other-{i}", f"Wedding Dress {i}", 5000, "Red", "wedding")
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


def test_sparse_compound_match_keeps_occasion_and_color():
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

    assert not relaxed.dropped_occasion
    assert relaxed.effective_color == "pink"
    assert not relaxed.dropped_color
    assert relaxed.result.total == 2
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
