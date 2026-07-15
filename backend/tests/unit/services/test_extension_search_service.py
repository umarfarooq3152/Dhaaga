from unittest.mock import AsyncMock

import pytest

from app.schemas.extension import CatalogRanking, ExtensionIntent
from app.errors import ExternalServiceError
from app.services.extension_catalog_service import ExtensionCatalog
from app.services.extension_search_service import ExtensionSearchError, ExtensionSearchService


def shopify_product(
    product_id: int,
    title: str,
    variants: list[dict],
    *,
    product_type: str = "T-Shirts",
    tags: list[str] | str | None = None,
) -> dict:
    return {
        "id": product_id,
        "title": title,
        "handle": title.lower().replace(" ", "-"),
        "body_html": "<p>Everyday fashion.</p>",
        "product_type": product_type,
        "tags": tags or ["Casual", "Weekend"],
        "images": [{"src": f"https://cdn.example.com/{product_id}.jpg"}],
        "options": [
            {"name": "Color", "values": ["Black", "Blue"]},
            {"name": "Size", "values": ["S", "M"]},
        ],
        "variants": variants,
    }


def variant(variant_id: int, color: str, size: str, price: float, available: bool = True) -> dict:
    return {
        "id": variant_id,
        "title": f"{color} / {size}",
        "option1": color,
        "option2": size,
        "price": str(price),
        "available": available,
    }


class FakeProvider:
    def __init__(self, intent: ExtensionIntent, rankings: list[CatalogRanking] | None = None):
        self.intent = intent
        self.rankings = rankings or []
        self.parse_intent = AsyncMock(return_value=intent)
        self.rank_candidates = AsyncMock(return_value=self.rankings)


def service_for(
    products: list[dict],
    provider: FakeProvider,
    capped: bool = False,
    result_limit: int = 12,
):
    catalog = AsyncMock()
    catalog.get_catalog.return_value = ExtensionCatalog(products=products, capped=capped)
    return ExtensionSearchService(
        catalog_service=catalog,
        intent_provider=provider,
        allowed_domains={"outfitters.com.pk", "www.outfitters.com.pk"},
        rank_candidate_limit=60,
        result_limit=result_limit,
    )


@pytest.mark.asyncio
async def test_filters_color_size_and_price_on_the_same_available_variant():
    false_conjunction = shopify_product(
        1,
        "Core T Shirt",
        [variant(11, "Black", "S", 2500), variant(12, "Blue", "M", 2500)],
    )
    exact = shopify_product(
        2,
        "Essential T Shirt",
        [
            variant(21, "Black", "M", 3200),
            variant(22, "Black", "M", 2800),
            variant(23, "Black", "M", 2600, available=False),
        ],
    )
    provider = FakeProvider(
        ExtensionIntent(category="t shirt", color="black", size="M", priceMax=3000)
    )

    response = await service_for([false_conjunction, exact], provider).search(
        "black t-shirt, size M, under 3000", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["2"]
    assert response.products[0].price == 2800
    assert "size M" in response.products[0].reason
    provider.rank_candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_extension_base_blue_excludes_other_blue_shades():
    base = shopify_product(1, "Blue Oxford Shirt", [variant(11, "Blue", "M", 2500)])
    dark = shopify_product(2, "Dark Blue Oxford Shirt", [variant(21, "Dark Blue", "M", 2500)])
    light = shopify_product(3, "Light Blue Oxford Shirt", [variant(31, "Light Blue", "M", 2500)])
    provider = FakeProvider(ExtensionIntent(category="shirt", color="blue"))

    response = await service_for([dark, light, base], provider).search(
        "basic blue shirt", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]


@pytest.mark.asyncio
async def test_descriptive_search_ranks_reconciled_candidate_ids():
    products = [
        shopify_product(1, "Olive Weekend Shirt", [variant(11, "Olive", "M", 2500)]),
        shopify_product(2, "Black Formal Shirt", [variant(21, "Black", "M", 2700)]),
    ]
    provider = FakeProvider(
        ExtensionIntent(descriptive="earthy for a casual weekend"),
        [
            CatalogRanking(id="1", score=9, reason="Olive tones and casual tags fit the weekend vibe."),
            CatalogRanking(id="unknown", score=10, reason="Must be ignored."),
            CatalogRanking(id="2", score=3, reason="A weaker metadata match."),
        ],
    )

    response = await service_for(products, provider).search(
        "something earthy for a casual weekend", "https://www.outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1", "2"]
    assert response.meta.store_domain == "outfitters.com.pk"
    assert response.products[0].score == 9


@pytest.mark.asyncio
async def test_refinement_passes_previous_intent_to_provider():
    product = shopify_product(1, "Blue Shirt", [variant(11, "Blue", "M", 2500)])
    previous = ExtensionIntent(category="shirt", color="black", size="M")
    provider = FakeProvider(ExtensionIntent(category="shirt", color="blue", size="M"))

    response = await service_for([product], provider).search(
        "blue instead", "https://outfitters.com.pk", previous
    )

    assert response.intent.color == "blue"
    provider.parse_intent.assert_awaited_once_with("blue instead", previous)


@pytest.mark.asyncio
async def test_descriptive_ranking_failure_keeps_deterministic_results():
    product = shopify_product(1, "Olive Weekend Shirt", [variant(11, "Olive", "M", 2500)])
    provider = FakeProvider(ExtensionIntent(category="shirt", descriptive="earthy weekend"))
    provider.rank_candidates.side_effect = ExternalServiceError("rate limited", service="groq")

    response = await service_for([product], provider).search(
        "earthy weekend shirt", "https://outfitters.com.pk"
    )

    assert [item.id for item in response.products] == ["1"]
    assert response.products[0].reason


@pytest.mark.asyncio
async def test_descriptive_results_fill_beyond_bounded_ai_ranking_batch():
    products = [
        shopify_product(
            product_id,
            f"Casual Polo {product_id}",
            [variant(product_id * 10, "Olive", "M", 2000 + product_id)],
            product_type="Polo Shirts",
        )
        for product_id in range(1, 31)
    ]
    provider = FakeProvider(
        ExtensionIntent(category="polo", descriptive="casual weekend"),
        [
            CatalogRanking(id=str(product_id), score=8, reason="Casual metadata fits the request.")
            for product_id in range(1, 25)
        ],
    )

    response = await service_for(products, provider, result_limit=40).search(
        "casual weekend polos", "https://outfitters.com.pk"
    )

    ranking_candidates = provider.rank_candidates.await_args.args[1]
    assert len(ranking_candidates) == 24
    assert len(response.products) == 30
    assert {item.id for item in response.products} == {str(item) for item in range(1, 31)}


@pytest.mark.asyncio
async def test_descriptive_intent_does_not_relax_hard_constraints():
    product = shopify_product(1, "Olive Shirt", [variant(11, "Olive", "S", 4000)])
    provider = FakeProvider(
        ExtensionIntent(color="brown", size="M", priceMax=3000, descriptive="earthy"),
        [CatalogRanking(id="1", score=7, reason="The olive tone supports an earthy look.")],
    )

    response = await service_for([product], provider, capped=True).search(
        "brown size M under 3000, earthy", "https://outfitters.com.pk"
    )

    assert response.products == []
    assert response.meta.relaxed is False
    assert response.meta.relaxed_filters == []
    assert response.meta.catalog_capped is True
    assert "results may be partial" in response.notice


@pytest.mark.asyncio
async def test_mehndi_intent_uses_event_appropriate_products_without_literal_tag():
    festive = shopify_product(
        1, "Mirror Work Sharara", [variant(11, "Black", "M", 5000)],
        product_type="Sharara", tags=["Embroidered", "Traditional"],
    )
    plain = shopify_product(
        2, "Plain Sharara", [variant(21, "Black", "M", 4000)],
        product_type="Sharara", tags=["Basics"],
    )
    provider = FakeProvider(ExtensionIntent(occasion="mehndi"))

    response = await service_for([plain, festive], provider).search(
        "cousin's mehndi", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert response.intent.occasion == "mehndi"
    assert "mehndi" in response.products[0].reason.lower()


@pytest.mark.asyncio
async def test_audience_switch_returns_only_requested_department_products():
    mens = shopify_product(
        1, "Embroidered Kurta", [variant(11, "Green", "M", 5000)],
        product_type="Kurta", tags=["Men", "Embroidered"],
    )
    womens = shopify_product(
        2, "Embroidered Kurta", [variant(21, "Green", "M", 5000)],
        product_type="Kurta", tags=["Women", "Embroidered"],
    )
    provider = FakeProvider(ExtensionIntent(audience="men", category="kurta"))

    response = await service_for([womens, mens], provider).search(
        "show men's instead", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert "men's department" in response.products[0].reason.lower()


@pytest.mark.asyncio
async def test_structured_only_miss_returns_a_true_empty_result():
    product = shopify_product(1, "Blue Shirt", [variant(11, "Blue", "S", 4000)])
    provider = FakeProvider(ExtensionIntent(color="black", size="M", priceMax=3000))
    response = await service_for([product], provider).search(
        "black size M under 3000", "https://outfitters.com.pk"
    )
    assert response.products == []
    assert response.meta.relaxed is False


@pytest.mark.asyncio
async def test_extension_excludes_kids_products_until_it_has_a_kids_flow():
    kids = shopify_product(
        1,
        "Toddler Olive Shirt",
        [variant(11, "Olive", "M", 2500)],
        tags=["Kids", "Casual"],
    )
    provider = FakeProvider(ExtensionIntent(category="shirt"))
    response = await service_for([kids], provider).search(
        "olive shirt", "https://outfitters.com.pk"
    )
    assert response.products == []


@pytest.mark.asyncio
async def test_extension_returns_only_age_compatible_kids_products():
    age_five = shopify_product(
        1,
        "Kids Formal Wide Leg Pants",
        [variant(11, "Black", "5-6Y", 2500)],
        product_type="TROUSERS",
        tags=["Kids", "5-6Y", "Formal"],
    )
    age_five["options"][1] = {"name": "Size", "values": ["5-6Y"]}
    too_old = shopify_product(
        2,
        "Junior Formal Pants",
        [variant(21, "Black", "10-12Y", 3000)],
        product_type="TROUSERS",
        tags=["Kids", "10-12Y", "Formal"],
    )
    too_old["options"][1] = {"name": "Size", "values": ["10-12Y"]}
    provider = FakeProvider(
        ExtensionIntent(category="pants", wantsKids=True, childAgeMonths=60)
    )

    response = await service_for([too_old, age_five], provider).search(
        "formal pants for my 5 year old kid", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert "kids' range" in response.products[0].reason.lower()


@pytest.mark.asyncio
async def test_extension_can_return_footwear_without_admitting_other_non_apparel():
    shoes = shopify_product(
        1,
        "Chunky Suede Loafers",
        [variant(11, "Black", "42", 5500)],
        product_type="CLOSED SHOES",
        tags=["Men", "Formal"],
    )
    perfume = shopify_product(
        2,
        "Noir Fragrance",
        [variant(21, "Black", "M", 4500)],
        product_type="FRAGRANCES",
    )
    provider = FakeProvider(ExtensionIntent(category="shoes"))

    response = await service_for([perfume, shoes], provider).search(
        "formal shoes", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]


@pytest.mark.asyncio
async def test_sleeves_matches_outfitters_compact_half_sleeve_tag():
    sleeved = shopify_product(
        1,
        "Basic Raglan T-Shirt",
        [variant(11, "Black", "M", 2500)],
        tags=["Men", "M-TS-RegHalfSleeveXXL", "T-Shirts"],
    )
    sleeveless = shopify_product(
        2,
        "Sleeveless Ribbed Dress",
        [variant(21, "Black", "M", 3500)],
        product_type="DRESSES",
        tags=["Women", "Sleeveless"],
    )
    provider = FakeProvider(ExtensionIntent(category="sleeve"))

    response = await service_for([sleeveless, sleeved], provider).search(
        "sleeves", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]


@pytest.mark.asyncio
async def test_empty_intent_stops_before_catalog_fetch():
    provider = FakeProvider(ExtensionIntent())
    service = service_for([], provider)
    with pytest.raises(ExtensionSearchError, match="Add a product") as caught:
        await service.search("hello", "https://outfitters.com.pk")
    assert caught.value.code == "EMPTY_INTENT"
    service._catalog_service.get_catalog.assert_not_awaited()


@pytest.mark.parametrize(
    "origin",
    [
        "http://outfitters.com.pk",
        "https://evil.example",
        "https://outfitters.com.pk.evil.example",
        "https://user:pass@outfitters.com.pk",
        "javascript:alert(1)",
    ],
)
def test_rejects_untrusted_store_origins(origin: str):
    provider = FakeProvider(ExtensionIntent(category="shirt"))
    with pytest.raises(ExtensionSearchError) as caught:
        service_for([], provider).validate_store_origin(origin)
    assert caught.value.code == "UNSUPPORTED_STORE"
