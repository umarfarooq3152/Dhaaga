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
    colors: list[str] | None = None,
    department: str | None = None,
    color_images: dict[str, str] | None = None,
    occasion: str = "casual",
) -> Product:
    return Product(
        id=f"{brand}:{external_id}",
        name=name,
        description=description,
        price=price,
        colors=colors or [],
        department=department,
        color_images=color_images or {},
        sizes=[],
        occasion=occasion,
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

    assert [item.name for item in result.items] == ["Black Knitted Polo T-Shirt"]


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

    assert [item.name for item in result.items] == ["AJPR-27"]


def test_shopify_tags_match_ranks_above_description_only_match():
    products = [
        _product("brand-a", "1", "Basic Pique Top", 1349, shopify_tags=["Men", "men-polo", "POLOS"]),
        _product("brand-b", "1", "Random Top", 990, description="Comes with a polo-style collar option."),
    ]

    result = SearchService.search(products, query="polo", page=1, page_size=10)

    assert [item.name for item in result.items] == ["Basic Pique Top"]


def test_daaku_vibe_maps_to_relevant_apparel_instead_of_empty_results():
    kurta = _product("brand-a", "1", "Textured Kurta", 4000, category="Kurta")
    unrelated = _product("brand-b", "1", "Basic T-Shirt", 1200, category="T-Shirts")

    result = SearchService.search(
        [kurta, unrelated], query="dress up like a bandit for daaku day", page_size=10
    )

    assert result.items == [kurta]


def test_specific_color_collapses_base_and_color_named_duplicate():
    base = _product("brand-a", "1", "Classic Oxford Shirt", 3000, colors=["Black"])
    black = _product("brand-a", "2", "Classic Oxford Shirt Black", 3200, colors=["Black"])

    result = SearchService.search([base, black], query="shirt", color="black", page_size=10)

    assert result.total == 1
    assert len(result.items) == 1


def test_color_filter_never_returns_another_color():
    yellow = _product("brand-a", "1", "Summer Dress", 3000, colors=["Yellow"])
    blue = _product("brand-b", "1", "Summer Dress", 2800, colors=["Blue"])
    yellow_shirt = _product("brand-c", "1", "Oxford Shirt", 2500, colors=["Yellow"])

    result = SearchService.search(
        [yellow, blue, yellow_shirt], query="dress", color="yellow", page_size=10
    )

    assert result.items == [yellow]


def test_color_filter_uses_matching_variant_image():
    product = _product(
        "brand-a", "1", "Summer Dress", 3000,
        colors=["Blue", "Yellow"],
        color_images={
            "blue": "https://example.com/blue.jpg",
            "yellow": "https://example.com/yellow.jpg",
        },
    )

    result = SearchService.search([product], query="dress", color="yellow", page_size=10)

    assert result.items[0].image == "https://example.com/yellow.jpg"


def test_generic_shirt_does_not_absorb_polos_or_tshirts():
    shirt = _product("brand-a", "1", "Oxford Shirt", 3000, category="Men Shirt")
    polo = _product("brand-b", "1", "Johnny Collar Polo", 3200, category="Polo Shirts")
    tee = _product("brand-c", "1", "Graphic T-Shirt", 1800, category="T-Shirts")

    result = SearchService.search([polo, tee, shirt], category="shirt", page_size=10)

    assert result.items == [shirt]


def test_broad_top_keeps_real_top_subfamilies_but_not_unrelated_garments():
    crop = _product("brand-a", "1", "Ribbed Crop Top", 2000, category="Crop Tops")
    blouse = _product("brand-b", "1", "Silk Blouse", 3500, category="Blouses")
    trouser = _product("brand-c", "1", "Wide Leg Trouser", 3000, category="Trousers")

    result = SearchService.search([trouser, crop, blouse], category="top", page_size=10)

    assert result.items == [crop, blouse]


def test_basic_blue_excludes_light_dark_and_navy_shades():
    base = _product("brand-a", "1", "Oxford Shirt", 3000, colors=["Blue"])
    dark = _product("brand-b", "1", "Oxford Shirt", 3000, colors=["Dark Blue"])
    light = _product("brand-c", "1", "Oxford Shirt", 3000, colors=["Light Blue"])
    navy = _product("brand-d", "1", "Oxford Shirt", 3000, colors=["Navy"])

    result = SearchService.search(
        [dark, light, navy, base], query="shirt", color="basic blue", page_size=10
    )

    assert result.items == [base]


def test_womenswear_filter_excludes_explicit_menswear_product():
    womens = _product("brand-a", "1", "Linen Kurta", 3000, department="women")
    mens = _product("brand-b", "1", "Linen Kurta", 2800, department="men")

    result = SearchService.search(
        [mens, womens], query="kurta", department="women", page_size=10
    )

    assert result.items == [womens]


def test_gendered_search_excludes_products_with_unknown_audience():
    mens = _product("brand-a", "1", "Men's Formal Kurta", 4500, department="men")
    unknown_kurti = _product(
        "generation", "1", "Threaded Grace Kurti", 2600, category="Kurti"
    )

    result = SearchService.search(
        [unknown_kurti, mens], occasion="nikah", department="men", page_size=10
    )

    assert result.items == [mens]


def test_stale_non_apparel_cache_entries_are_removed_during_search():
    kurta = _product(
        "brand-a", "1", "Cream Formal Kurta", 4500,
        category="Kurta", department="men",
    )
    towel = _product(
        "brand-b", "1", "Frost Beige 3 Piece Embroidered Towel Set", 7000,
        category="Ideas Home", shopify_tags=["Towel Set"], department="men",
    )

    result = SearchService.search(
        [towel, kurta], occasion="nikah", department="men", page_size=10
    )

    assert result.items == [kurta]


def test_semantic_query_reranks_the_better_vibe_without_bypassing_filters():
    bright = _product(
        "brand-a", "1", "Yellow Mirror Work Kurta", 5000,
        category="Kurta", department="women", occasion="mehndi",
        description="A bright embroidered festive kurta for celebrations.",
    )
    plain = _product(
        "brand-b", "1", "Plain Beige Kurta", 4500,
        category="Kurta", department="women", occasion="mehndi",
        description="A minimal neutral everyday kurta.",
    )
    wrong_audience = _product(
        "brand-c", "1", "Bright Embroidered Kurta", 4000,
        category="Kurta", department="men", occasion="mehndi",
        description="Bright festive embroidery.",
    )

    result = SearchService.search(
        [plain, wrong_audience, bright],
        occasion="mehndi",
        department="women",
        semantic_query="bright embroidered women's kurta for mehndi",
        page_size=10,
    )

    assert result.items == [bright, plain]


def test_size_filter_normalizes_common_store_labels():
    medium = _product("brand-a", "1", "Oxford Shirt", 3000).model_copy(
        update={"sizes": ["Small", "Medium", "Large"]}
    )
    extra_large = _product("brand-b", "1", "Oxford Shirt", 3200).model_copy(
        update={"sizes": ["2XL"]}
    )

    result = SearchService.search([medium, extra_large], query="shirt", size="M")
    xxl_result = SearchService.search([medium, extra_large], query="shirt", size="XXL")

    assert result.items == [medium]
    assert xxl_result.items == [extra_large]


def test_formal_search_excludes_tshirts_and_jeans_even_with_premium_words():
    formal_shirt = _product("brand-a", "1", "Oxford Button-down Shirt", 5000)
    silk_tshirt = _product("brand-b", "1", "Silk T-Shirt", 7000)
    jeans = _product("brand-c", "1", "Premium Denim Jeans", 7000)

    result = SearchService.search(
        [formal_shirt, silk_tshirt, jeans], query="formal", page_size=10
    )

    assert result.items == [formal_shirt]


def test_casual_search_excludes_inherently_formal_eastern_items():
    hoodie = _product("brand-a", "1", "Cotton Hoodie", 3000)
    sherwani = _product("brand-b", "1", "Plain Sherwani", 15000)
    result = SearchService.search([hoodie, sherwani], query="casual", page_size=10)

    assert result.items == [hoodie]


def test_activewear_and_eastern_western_filters_use_taxonomy_rules():
    gym_tee = _product("brand-a", "1", "Dri-Fit Training Tee", 3000)
    lawn_kurta = _product("brand-b", "1", "Printed Lawn Kurta", 4000)
    result = SearchService.search([gym_tee, lawn_kurta], query="gym clothes", page_size=10)
    assert result.items == [gym_tee]

    eastern = SearchService.search([gym_tee, lawn_kurta], query="eastern wear", page_size=10)
    assert eastern.items == [lawn_kurta]


def test_primary_garment_is_hard_but_secondary_styling_item_is_not_returned():
    jeans = _product("brand-a", "1", "Baggy Jeans", 4000, category="Jeans")
    shirt = _product("brand-b", "1", "Black Oxford Shirt", 3000, category="Shirts")

    jeans_result = SearchService.search(
        [shirt, jeans],
        query="dark blue baggy jeans I can wear with a black shirt",
        page_size=10,
    )
    shirt_result = SearchService.search(
        [jeans, shirt], query="black shirt with blue jeans", page_size=10
    )

    assert jeans_result.items == [jeans]
    assert shirt_result.items == [shirt]


def test_store_knitwear_category_is_a_valid_sweater_match():
    sweater = _product("brand-a", "1", "Crew Neck Knit", 4000, category="KNITWEAR")
    shirt = _product("brand-b", "1", "Oxford Shirt", 3000, category="Shirts")

    result = SearchService.search([shirt, sweater], category="sweater", page_size=10)

    assert result.items == [sweater]
