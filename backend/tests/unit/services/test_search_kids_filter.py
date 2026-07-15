"""Tests for the kids-item filter in SearchService.

Kids apparel is no longer excluded from the catalog entirely (it used to
be, on the assumption Dhaaga had no kids' flow at all) — it's kept and
tagged (Product.is_kids), then filtered OUT of an ordinary adult search
by default and filtered TO when a shopper indicates they're buying for a
child (SessionState.wants_kids -> SearchService.search(kids=True)).
"""

from app.schemas.product import Product
from app.services.search_service import SearchService


def _product(
    brand: str,
    external_id: str,
    name: str,
    price: float,
    is_kids: bool = False,
    sizes: list[str] | None = None,
) -> Product:
    return Product(
        id=f"{brand}:{external_id}",
        name=name,
        description="",
        price=price,
        colors=[],
        sizes=sizes or [],
        occasion="casual",
        category=None,
        tags=[],
        shopify_tags=[],
        is_kids=is_kids,
        image="https://example.com/1.jpg",
        secondaryImage=None,
        product_url="https://example.com/products/1",
    )


def test_adult_search_excludes_kids_items_by_default():
    products = [
        _product("brand-a", "1", "Embroidered Kurta", 3000, is_kids=False),
        _product("brand-a", "2", "Kids Embroidered Kurta", 1500, is_kids=True),
    ]

    result = SearchService.search(products, query="kurta", page=1, page_size=10)

    assert result.total == 1
    assert result.items[0].name == "Embroidered Kurta"


def test_kids_true_returns_only_kids_items():
    products = [
        _product("brand-a", "1", "Embroidered Kurta", 3000, is_kids=False),
        _product("brand-a", "2", "Kids Embroidered Kurta", 1500, is_kids=True),
    ]

    result = SearchService.search(products, query="kurta", page=1, page_size=10, kids=True)

    assert result.total == 1
    assert result.items[0].name == "Kids Embroidered Kurta"


def test_search_by_brands_also_respects_kids_filter():
    products = [
        _product("brand-a", "1", "Adult Shirt", 3000, is_kids=False),
        _product("brand-a", "2", "Kids Shirt", 1500, is_kids=True),
    ]

    adult_result = SearchService.search_by_brands(products, ["brand-a"], page=1, page_size=10)
    assert [p.name for p in adult_result.items] == ["Adult Shirt"]

    kids_result = SearchService.search_by_brands(products, ["brand-a"], page=1, page_size=10, kids=True)
    assert [p.name for p in kids_result.items] == ["Kids Shirt"]


def test_exact_child_age_excludes_older_kids_products():
    products = [
        _product("brand-a", "2", "Toddler Kurta", 1500, True, ["1-2Y", "2-3Y"]),
        _product("brand-a", "12", "Junior Kurta", 1900, True, ["10-12Y", "12-14Y"]),
        _product("brand-a", "unknown", "Generic Kids Kurta", 1700, True, ["S", "M"]),
    ]

    result = SearchService.search(
        products,
        query="kurta",
        page=1,
        page_size=10,
        kids=True,
        child_age_months=24,
    )

    assert [p.name for p in result.items] == ["Toddler Kurta"]


def test_child_age_is_not_relaxed_when_other_filters_are_relaxed():
    from app.schemas.session import SessionState
    from app.services.session_service import _search_with_relax

    products = [
        _product("brand-a", "2", "Pink Toddler Kurta", 1500, True, ["2-3Y"]),
        *[
            _product("brand-b", f"12-{i}", f"Pink Junior Kurta {i}", 1900, True, ["10-12Y"])
            for i in range(15)
        ],
    ]
    for product in products:
        product.colors = ["Pink"]

    relaxed = _search_with_relax(
        products,
        SessionState(
            wants_kids=True,
            child_age_months=24,
            color_preference="pink",
            style_descriptors=["kurta"],
        ),
        page_size=20,
    )

    assert [p.name for p in relaxed.result.items] == ["Pink Toddler Kurta"]
