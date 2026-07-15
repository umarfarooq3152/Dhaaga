"""Tests for brand-diversified ranking in SearchService.

Regression coverage for a real bug: when keyword scores tie (the common
case for pure structured/budget queries with no fuzzy style words), a flat
sort fell back to product name — clustering results by whichever brand's
naming convention happened to sort first alphabetically, instead of
surfacing a mix of brands.
"""

from app.schemas.product import Product
from app.services.search_service import SearchService


def _product(brand: str, external_id: str, name: str, price: float) -> Product:
    return Product(
        id=f"{brand}:{external_id}",
        name=name,
        description="",
        price=price,
        colors=[],
        sizes=[],
        occasion="eid",
        tags=[],
        image="https://example.com/1.jpg",
        secondaryImage=None,
        product_url="https://example.com/products/1",
    )


def test_results_are_not_dominated_by_a_single_brand():
    # brand-a has many cheap products whose names alphabetically sort first —
    # exactly the real-world pattern that caused the bug.
    products = [_product("brand-a", str(i), f"2 PIECE SUIT {i}", 1000 + i) for i in range(10)]
    products += [_product("brand-b", str(i), f"Kurta {i}", 1000 + i) for i in range(3)]
    products += [_product("brand-c", str(i), f"Sherwani {i}", 1000 + i) for i in range(3)]

    result = SearchService.search(products, query="", page=1, page_size=10)

    top_ten_brands = [p.id.split(":")[0] for p in result.items[:10]]
    # All three brands should appear in the first 10 results, not just brand-a.
    assert "brand-b" in top_ten_brands
    assert "brand-c" in top_ten_brands
    # No single brand should monopolize the top slice when others have matches.
    assert top_ten_brands.count("brand-a") < 10


def test_diversification_preserves_price_order_within_a_brand():
    products = [
        _product("brand-a", "1", "Expensive Suit", 9000),
        _product("brand-a", "2", "Cheap Suit", 1000),
        _product("brand-a", "3", "Mid Suit", 5000),
    ]

    result = SearchService.search(products, query="", page=1, page_size=10)

    prices = [p.price for p in result.items]
    assert prices == sorted(prices)


def test_single_brand_still_returns_all_matches():
    products = [_product("brand-a", str(i), f"Item {i}", 1000 + i) for i in range(5)]

    result = SearchService.search(products, query="", page=1, page_size=10)

    assert result.total == 5
    assert len(result.items) == 5


def test_relevant_keyword_matches_rank_before_irrelevant_filler():
    # Real bug: round-robining across ALL brands regardless of score meant
    # a brand with zero "lehenga" matches still contributed its top item
    # into round 0, surfacing an unrelated product (a hand towel) ahead of
    # or alongside genuine matches. Relevant items must always rank first.
    products = [
        _product("brand-a", "1", "Elegant Wedding Lehenga", 40000),
        _product("brand-b", "1", "HOME | HAND TOWEL", 500),
        _product("brand-c", "1", "Casual Tshirt", 750),
        _product("brand-d", "1", "Grey Socks", 300),
    ]

    result = SearchService.search(products, query="lehenga", page=1, page_size=10)

    assert result.items[0].name == "Elegant Wedding Lehenga"
    irrelevant_names = {"HOME | HAND TOWEL", "Casual Tshirt", "Grey Socks"}
    assert {p.name for p in result.items[1:]} == irrelevant_names


def test_query_matching_nothing_returns_zero_results_not_the_whole_catalog():
    # Real bug: searching "sherwani" (a category none of the registered
    # brands carry) scored every product 0, so the old filler-always-
    # appended logic surfaced the entire unrelated catalog — literally
    # socks and hair ties — dressed up to look like real matches.
    products = [
        _product("brand-a", "1", "Grey Invisible Socks", 240),
        _product("brand-b", "1", "Handcrafted Bloom Hair Tie", 200),
        _product("brand-c", "1", "Ladies Tights", 500),
    ]

    result = SearchService.search(products, query="sherwani", page=1, page_size=10)

    assert result.total == 0
    assert result.items == []


def test_multiple_relevant_matches_still_diversify_by_brand():
    products = [
        _product("brand-a", "1", "Wedding Lehenga A", 40000),
        _product("brand-a", "2", "Wedding Lehenga A2", 42000),
        _product("brand-b", "1", "Wedding Lehenga B", 35000),
        _product("brand-c", "1", "Unrelated Filler", 500),
    ]

    result = SearchService.search(products, query="lehenga wedding", page=1, page_size=10)

    top_two_brands = {p.id.split(":")[0] for p in result.items[:2]}
    assert top_two_brands == {"brand-a", "brand-b"}
    assert result.items[-1].name == "Unrelated Filler"
