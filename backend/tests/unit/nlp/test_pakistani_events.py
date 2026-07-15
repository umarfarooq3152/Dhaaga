from app.nlp.pakistani_events import event_match_score, extract_event
from app.schemas.product import Product
from app.services.search_service import SearchService


def _product(name: str, *, category: str = "", colors=None, tags=None) -> Product:
    return Product(
        id=f"test:{name}", name=name, category=category, colors=colors or [],
        tags=tags or [], description="", price=5000, image="https://example.com/a.jpg",
        product_url="https://example.com/a",
    )


def test_pakistani_event_aliases_normalize_to_canonical_names():
    cases = {
        "cousin's dholki": "mehndi",
        "outfit for my mayun": "mehndi",
        "nikkah ceremony": "nikah",
        "shaadi clothes": "baraat",
        "valima reception": "walima",
        "mangni look": "engagement",
        "14 August kurta": "independence day",
        "convocation outfit": "graduation",
    }
    for query, expected in cases.items():
        assert extract_event(query) == expected


def test_mehndi_accepts_colorful_festive_garment():
    product = _product(
        "Mirror Work Sharara", category="Sharara", colors=["Yellow"],
        tags=["embroidered", "traditional"],
    )
    assert event_match_score(product, "mehndi") == 1.0


def test_mehndi_rejects_plain_or_unrelated_items():
    plain_kurta = _product("Plain Kurta", category="Kurta", colors=["Grey"])
    stencil = _product("Mehndi Stencil", category="Accessories", colors=["Yellow"])
    assert event_match_score(plain_kurta, "mehndi") == 0.0
    # Literal event words alone are insufficient for a non-garment at search
    # time; ingestion separately excludes stencils from the catalog.
    assert event_match_score(stencil, "mehndi") == 1.0


def test_mehndi_search_curates_inferred_products_without_literal_event_tag():
    festive = _product(
        "Mirror Work Sharara", category="Sharara", colors=["Yellow"],
        tags=["embroidered", "traditional"],
    )
    plain = _product("Plain Grey Kurta", category="Kurta", colors=["Grey"])
    unrelated = _product("Yellow Oxford Shirt", category="Shirt", colors=["Yellow"])

    result = SearchService.search(
        [plain, unrelated, festive], occasion="mehndi", page_size=10
    )

    assert result.items == [festive]
