"""Tests for SearchService's keyword relevance scoring.

Regression coverage for two real bugs found via live search: (1) plain
substring matching let a query keyword match inside an unrelated word
(e.g. "polo" inside "apology"), and (2) matching equally against the raw
scraped HTML description let generic fabric/care boilerplate ("knitted",
"breathable") make an unrelated garment (e.g. a camisole) score as a
partial match for a completely different garment type (a polo).
"""

from app.schemas.product import Product
from app.services.search_service import SearchService


def _product(
    brand: str,
    external_id: str,
    name: str,
    price: float,
    description: str = "",
    category: str | None = None,
    shopify_tags: list[str] | None = None,
) -> Product:
    return Product(
        id=f"{brand}:{external_id}",
        name=name,
        description=description,
        price=price,
        colors=[],
        sizes=[],
        occasion="casual",
        category=category,
        tags=[],
        shopify_tags=shopify_tags or [],
        image="https://example.com/1.jpg",
        secondaryImage=None,
        product_url="https://example.com/products/1",
    )


def test_keyword_does_not_match_inside_an_unrelated_word():
    # Real bug: searching "polo" matched "Not Sorry", an oversized t-shirt
    # whose description contains the word "apology" — "polo" is a
    # substring of "apology" but is not the word "polo". A genuine
    # non-match like this must not appear in results at all (score 0 is
    # excluded entirely, not just ranked last as filler).
    products = [
        _product("brand-a", "1", "Basic Smart Fit Polo Top", 990),
        _product(
            "brand-b", "1", "Not Sorry",
            2000, description="The design plays with contrast, zero apology.",
        ),
    ]

    result = SearchService.search(products, query="polo", page=1, page_size=10)

    assert result.total == 1
    assert result.items == [products[0]]


def test_description_only_match_ranks_below_title_match():
    # Real bug: a camisole's description mentioned "knitted" as a fabric
    # detail, scoring it as a partial match for "knitted polo" alongside
    # actual polos — an unrelated garment type shouldn't rank as if
    # relevant just because a fabric word appears in its scraped HTML.
    products = [
        _product("brand-a", "1", "Black Knitted Polo T-Shirt", 1650, description="Soft knit cotton blend."),
        _product(
            "brand-b", "1", "Basic Camisole", 649,
            description="Ribbed straps, a scoop neck, straight-cut hem, knitted.",
        ),
    ]

    result = SearchService.search(products, query="knitted polo", page=1, page_size=10)

    assert result.items[0].name == "Black Knitted Polo T-Shirt"
    assert result.items[-1].name == "Basic Camisole"


def test_title_match_beats_description_only_match_for_single_keyword():
    products = [
        _product("brand-a", "1", "Polo Shirt", 1490),
        _product("brand-b", "1", "Random Top", 990, description="Comes with a polo-style collar option."),
    ]

    result = SearchService.search(products, query="polo", page=1, page_size=10)

    assert result.items[0].name == "Polo Shirt"


def test_category_match_scores_as_high_as_title_match():
    # Shopify's product_type is a precise merchant-set garment label —
    # a generically-named product in the right category should rank
    # alongside a product whose title literally says the keyword.
    products = [
        _product("brand-a", "1", "AJPR-27", 1590, category="Kurta"),
        _product("brand-b", "1", "Random Top", 990, description="Not a kurta at all."),
    ]

    result = SearchService.search(products, query="kurta", page=1, page_size=10)

    assert result.items[0].name == "AJPR-27"
    assert result.items[-1].name == "Random Top"


def test_shopify_tags_match_ranks_above_description_only_match():
    products = [
        _product("brand-a", "1", "Basic Pique Top", 1349, shopify_tags=["Men", "men-polo", "POLOS"]),
        _product("brand-b", "1", "Random Top", 990, description="Comes with a polo-style collar option."),
    ]

    result = SearchService.search(products, query="polo", page=1, page_size=10)

    assert result.items[0].name == "Basic Pique Top"
    assert result.items[-1].name == "Random Top"
