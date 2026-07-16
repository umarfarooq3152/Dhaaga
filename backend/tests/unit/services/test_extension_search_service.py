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
    assert "size m" in response.products[0].reason.lower()
    assert response.products[0].match_details.colors == ["Black"]
    assert response.products[0].match_details.sizes == ["M"]
    assert response.products[0].match_details.image_matches_color is False
    assert response.meta.mapped_count == 2
    assert response.meta.exact_count == 1
    provider.rank_candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_requested_color_uses_and_verifies_variant_specific_image():
    black_variant = variant(11, "Black", "M", 2800)
    black_variant["featured_image"] = {"src": "https://cdn.example.com/black.jpg"}
    product = shopify_product(1, "Core Shirt", [black_variant], product_type="SHIRTS")
    provider = FakeProvider(ExtensionIntent(category="shirt", color="black", size="M"))

    response = await service_for([product], provider).search(
        "black shirt size M", "https://outfitters.com.pk"
    )

    assert response.products[0].image_url == "https://cdn.example.com/black.jpg"
    assert response.products[0].match_details.image_matches_color is True


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
async def test_extension_accepts_either_of_two_requested_colors():
    brown = shopify_product(1, "Knitted Polo", [variant(11, "Brown", "M", 2500)], product_type="Polo")
    red = shopify_product(2, "Knitted Polo", [variant(21, "Red", "M", 2600)], product_type="Polo")
    black = shopify_product(3, "Knitted Polo", [variant(31, "Black", "M", 2700)], product_type="Polo")
    provider = FakeProvider(ExtensionIntent(category="polo", color="brown or red"))

    response = await service_for([black, red, brown], provider).search(
        "some knitted polos, brown or red", "https://outfitters.com.pk"
    )

    assert {product.id for product in response.products} == {"1", "2"}


@pytest.mark.asyncio
async def test_extension_formal_filter_excludes_tshirts():
    shirt = shopify_product(1, "Oxford Button Down Shirt", [variant(11, "White", "M", 5000)], product_type="Shirts")
    tee = shopify_product(2, "Silk T-Shirt", [variant(21, "White", "M", 7000)], product_type="T-Shirts")
    provider = FakeProvider(ExtensionIntent(category="t-shirt", descriptive="formal"))

    response = await service_for([shirt, tee], provider).search(
        "formal t-shirt", "https://outfitters.com.pk"
    )

    assert response.products == []


@pytest.mark.asyncio
async def test_extension_casual_filter_excludes_formal_products_when_matches_exist():
    casual = shopify_product(
        1,
        "Cotton Weekend Shirt",
        [variant(11, "Blue", "M", 3000)],
        product_type="Shirts",
        tags=["Casual"],
    )
    formal = shopify_product(
        2,
        "Oxford Formal Shirt",
        [variant(21, "Blue", "M", 5000)],
        product_type="Shirts",
        tags=["Formal"],
    )
    provider = FakeProvider(ExtensionIntent(category="shirt", descriptive="casual"))

    response = await service_for([formal, casual], provider).search(
        "casual shirts", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert response.meta.relaxed is False


@pytest.mark.asyncio
async def test_extension_uses_shared_fabric_and_embellishment_guide():
    plain = shopify_product(
        1,
        "Plain Lawn Kurta",
        [variant(11, "Green", "M", 3500)],
        product_type="KURTA",
        tags=["Lawn", "Everyday"],
    )
    festive = shopify_product(
        2,
        "Organza Kurta with Gota Handwork",
        [variant(21, "Green", "M", 8500)],
        product_type="KURTA",
        tags=["Organza", "Gota", "Handwork"],
    )
    provider = FakeProvider(ExtensionIntent(descriptive="party eastern"))

    response = await service_for([plain, festive], provider).search(
        "party eastern clothes", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["2"]
    assert "party" in response.products[0].reason.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "category", "product_type"),
    [
        ("belts", "belt", "BELTS"),
        ("sweater", "sweater", "KNITWEAR"),
        ("khussa", "shoes", "KHUSSA"),
    ],
)
async def test_outfitters_category_vocabulary_matches_store_labels(query, category, product_type):
    product = shopify_product(
        1,
        "Core Accessory" if category == "belt" else "Crew Neck Knit",
        [variant(11, "Black", "M", 2500)],
        product_type=product_type,
    )
    provider = FakeProvider(ExtensionIntent(category=category))

    response = await service_for([product], provider).search(
        query, "https://outfitters.com.pk"
    )

    assert [item.id for item in response.products] == ["1"]


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

    assert [product.id for product in response.products] == ["1"]
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
async def test_mehndi_intent_keeps_event_match_first_then_plain_near_match():
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

    assert [product.id for product in response.products] == ["1", "2"]
    assert response.meta.exact_count == 1
    assert response.intent.occasion == "mehndi"
    assert "mehndi" in response.products[0].reason.lower()
    assert response.products[1].match_details.occasion is None


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
async def test_formal_shoes_prioritize_formal_footwear_without_collapsing_category():
    loafers = shopify_product(
        1,
        "Chunky Suede Loafers",
        [variant(11, "Black", "42", 5500)],
        product_type="CLOSED SHOES",
        tags=["Men", "Formal"],
    )
    slides = shopify_product(
        2,
        "Textured Slides",
        [variant(21, "Black", "42", 2500)],
        product_type="OPEN SHOES",
        tags=["Men", "Casual"],
    )
    provider = FakeProvider(ExtensionIntent(category="shoes", descriptive="formal"))

    response = await service_for([slides, loafers], provider).search(
        "formal shoes", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert response.meta.relaxed is False


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
async def test_unavailable_fit_keeps_color_and_returns_truthful_near_match():
    blue_baggy = shopify_product(
        1,
        "Baggy Fit Jeans",
        [variant(11, "Denim Blue", "32", 4990)],
        product_type="JEANS",
        tags=["Men", "Baggy Fit"],
    )
    black_straight = shopify_product(
        2,
        "Straight Fit Jeans",
        [variant(21, "Black", "32", 4590)],
        product_type="JEANS",
        tags=["Men", "Straight Fit"],
    )
    provider = FakeProvider(ExtensionIntent(category="jeans", color="black", fit="baggy"))

    response = await service_for([black_straight, blue_baggy], provider).search(
        "baggy black jeans preferably", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["2"]
    assert response.meta.exact_count == 0
    assert response.meta.relaxed_filters == ["fit"]
    assert response.products[0].match_details.colors == ["Black"]
    assert response.products[0].match_details.fit is None


@pytest.mark.asyncio
async def test_exact_preference_tier_leads_color_correct_nearby_products():
    exact = shopify_product(
        1, "Baggy Fit Jeans", [variant(11, "Black", "32", 5990)],
        product_type="JEANS", tags=["Men", "Baggy Fit"],
    )
    wrong_fit = shopify_product(
        2, "Straight Fit Jeans", [variant(21, "Black", "32", 4590)],
        product_type="JEANS", tags=["Men", "Straight Fit"],
    )
    wrong_color = shopify_product(
        3, "Baggy Fit Jeans", [variant(31, "Blue", "32", 4990)],
        product_type="JEANS", tags=["Men", "Baggy Fit"],
    )
    provider = FakeProvider(ExtensionIntent(category="jeans", color="black", fit="baggy"))

    response = await service_for([wrong_fit, wrong_color, exact], provider).search(
        "black baggy jeans", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1", "2"]
    assert response.meta.exact_count == 1
    assert response.products[0].match_details.fit == "baggy"
    assert response.products[1].match_details.fit is None


@pytest.mark.asyncio
async def test_unavailable_color_returns_no_wrong_color_fallback():
    red = shopify_product(
        1, "Oxford Shirt", [variant(11, "Red", "M", 2990)],
        product_type="SHIRTS", tags=["Men", "Formal"],
    )
    provider = FakeProvider(ExtensionIntent(category="shirt", color="black"))

    response = await service_for([red], provider).search(
        "black shirt", "https://outfitters.com.pk"
    )

    assert response.products == []
    assert response.meta.relaxed is False
    assert response.meta.relaxed_filters == []
    assert response.notice is None


@pytest.mark.asyncio
async def test_unavailable_occasion_preserves_size_for_near_match():
    wrong_size = shopify_product(
        1, "Festive Shirt", [variant(11, "Blue", "S", 2990)],
        product_type="SHIRTS", tags=["Embroidered", "Traditional"],
    )
    right_size_plain = shopify_product(
        2, "Basic Shirt", [variant(21, "Blue", "M", 2490)],
        product_type="SHIRTS", tags=["Basics"],
    )
    provider = FakeProvider(ExtensionIntent(category="shirt", size="M", occasion="mehndi"))

    response = await service_for([wrong_size, right_size_plain], provider).search(
        "shirt size M for mehndi", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["2"]
    assert response.meta.exact_count == 0
    assert response.products[0].match_details.sizes == ["M"]
    assert response.products[0].match_details.occasion is None


@pytest.mark.asyncio
async def test_requested_apparel_family_is_a_hard_constraint():
    eastern = shopify_product(
        1,
        "Embroidered Kurta",
        [variant(11, "Green", "M", 4990)],
        product_type="KURTA",
        tags=["Men", "Eastern", "Embroidered"],
    )
    western = shopify_product(
        2,
        "Oxford Shirt",
        [variant(21, "Green", "M", 3990)],
        product_type="SHIRTS",
        tags=["Men", "Western", "Formal"],
    )
    provider = FakeProvider(ExtensionIntent(descriptive="eastern"))

    response = await service_for([western, eastern], provider).search(
        "show me eastern wear", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert response.meta.relaxed is False


@pytest.mark.asyncio
async def test_extension_broad_western_wear_spans_multiple_categories():
    products = [
        shopify_product(1, "Crew Neck T-Shirt", [variant(11, "Black", "M", 1990)], product_type="T-SHIRTS"),
        shopify_product(2, "Straight Denim Jeans", [variant(21, "Blue", "M", 3990)], product_type="JEANS"),
        shopify_product(3, "Cotton Day Dress", [variant(31, "White", "M", 4490)], product_type="DRESSES"),
        shopify_product(4, "Printed Lawn Kurta", [variant(41, "Green", "M", 3490)], product_type="KURTA"),
    ]
    provider = FakeProvider(ExtensionIntent(descriptive="western"))

    response = await service_for(products, provider).search(
        "show me western wear", "https://outfitters.com.pk"
    )

    assert {product.id for product in response.products} == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_extension_keeps_exact_occasion_first_then_adds_near_matches():
    exact = shopify_product(
        1,
        "Green Gota Kurta",
        [variant(11, "Green", "M", 5990)],
        product_type="KURTA",
        tags=["Gota", "Festive", "Traditional"],
    )
    near = shopify_product(
        2,
        "Black Plain Kurta",
        [variant(21, "Black", "M", 4990)],
        product_type="KURTA",
        tags=["Basics"],
    )
    provider = FakeProvider(ExtensionIntent(category="kurta", occasion="mehndi"))

    response = await service_for([near, exact], provider).search(
        "kurtas for mehndi", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1", "2"]
    assert response.meta.exact_count == 1
    assert response.meta.relaxed is True
    assert response.meta.relaxed_filters == ["occasion"]
    assert response.products[0].match_details.occasion == "mehndi"
    assert response.products[1].match_details.occasion is None
    assert "Exact matches are shown first" in response.notice


@pytest.mark.asyncio
async def test_activewear_request_excludes_plain_casual_items():
    training = shopify_product(
        1,
        "Dri Fit Training Tee",
        [variant(11, "Black", "M", 2990)],
        product_type="ACTIVEWEAR",
        tags=["Men", "Training", "Dri Fit"],
    )
    casual = shopify_product(
        2,
        "Basic Cotton Tee",
        [variant(21, "Black", "M", 1990)],
        product_type="T-SHIRTS",
        tags=["Men", "Casual", "Cotton"],
    )
    provider = FakeProvider(ExtensionIntent(descriptive="activewear"))

    response = await service_for([casual, training], provider).search(
        "activewear for training", "https://outfitters.com.pk"
    )

    assert [product.id for product in response.products] == ["1"]
    assert response.meta.relaxed is False


@pytest.mark.asyncio
async def test_requested_audience_excludes_unknown_and_wrong_departments():
    mens = shopify_product(
        1,
        "Men's Oxford Shirt",
        [variant(11, "White", "M", 3990)],
        product_type="SHIRTS",
        tags=["Men", "Formal"],
    )
    womens = shopify_product(
        2,
        "Women's Oxford Shirt",
        [variant(21, "White", "M", 3990)],
        product_type="SHIRTS",
        tags=["Women", "Formal"],
    )
    unknown = shopify_product(
        3,
        "Oxford Shirt",
        [variant(31, "White", "M", 3990)],
        product_type="SHIRTS",
        tags=["Formal"],
    )
    provider = FakeProvider(ExtensionIntent(category="shirt", audience="men"))

    response = await service_for([unknown, womens, mens], provider).search(
        "men's shirts", "https://outfitters.com.pk"
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
