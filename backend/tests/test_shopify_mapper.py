"""Tests for Shopify mapper and keyword tagger."""

import pytest

from app.nlp.keyword_matcher import extract_occasion, extract_tags, tag_product
from app.schemas.product import Product
from app.shopify.mapper import (
    extract_colors,
    extract_color_images,
    extract_sizes,
    html_to_plain_text,
    map_shopify_to_product,
)


# Sample Shopify product
SAMPLE_SHOPIFY_PRODUCT = {
    "id": 1234567890,
    "title": "Red Embroidered Eid Dress",
    "handle": "red-embroidered-eid-dress",
    "body_html": "<p>Beautiful red cotton dress with hand embroidery. Perfect for Eid celebrations.</p>",
    "images": [
        {"src": "https://example.com/image1.jpg"},
        {"src": "https://example.com/image2.jpg"},
    ],
    "options": [
        {
            "id": 1,
            "name": "Color",
            "values": ["Red", "Blue", "Green"],
        },
        {
            "id": 2,
            "name": "Size",
            "values": ["XS", "S", "M", "L", "XL"],
        },
    ],
    "variants": [
        {
            "id": 1,
            "title": "Red / S",
            "price": "5000",
        },
        {
            "id": 2,
            "title": "Blue / M",
            "price": "5000",
        },
    ],
}


class TestColorExtraction:
    """Test color extraction from Shopify products."""

    def test_extract_from_options(self):
        """Extract colors from options array."""
        colors = extract_colors(SAMPLE_SHOPIFY_PRODUCT)
        assert "Red" in colors
        assert "Blue" in colors
        assert "Green" in colors

    def test_extract_from_variants(self):
        """Extract colors from variant titles."""
        colors = extract_colors(SAMPLE_SHOPIFY_PRODUCT)
        # Should contain colors from both options and variants
        assert len(colors) > 0

    def test_default_color(self):
        """Return Default color for products with no colors."""
        colors = extract_colors({})
        assert colors == ["Default"]

    def test_extracts_variant_specific_color_images(self):
        product = {
            "options": [{"name": "Color", "values": ["Blue", "Yellow"]}],
            "images": [],
            "variants": [
                {
                    "option1": "Blue",
                    "featured_image": {"src": "https://example.com/blue.jpg"},
                },
                {
                    "option1": "Yellow",
                    "featured_image": {"src": "https://example.com/yellow.jpg"},
                },
            ],
        }
        assert extract_color_images(product) == {
            "blue": "https://example.com/blue.jpg",
            "yellow": "https://example.com/yellow.jpg",
        }


class TestSizeExtraction:
    """Test size extraction from Shopify products."""

    def test_extract_from_options(self):
        """Extract sizes from options array."""
        sizes = extract_sizes(SAMPLE_SHOPIFY_PRODUCT)
        assert "S" in sizes
        assert "M" in sizes
        assert "XL" in sizes

    def test_default_size(self):
        """Return One Size for products with no sizes."""
        sizes = extract_sizes({})
        assert sizes == ["One Size"]

    def test_extract_from_non_exact_size_option_name(self):
        # Real observed case: Gul Ahmed names its size option "Men Sizes",
        # which an exact match on "size"/"sizes" used to miss entirely,
        # silently falling back to "One Size" for every product.
        product = {
            "options": [{"id": 1, "name": "Men Sizes", "values": ["S", "M", "L"]}],
            "variants": [],
        }
        sizes = extract_sizes(product)
        assert sizes == ["L", "M", "S"]


class TestMapperBasic:
    """Test basic Shopify to Product mapping."""

    def test_shopify_description_html_becomes_readable_plain_text(self):
        raw = (
            '<ul><li><p data-path-to-node="3,0,0"><b>Adjustable Waist</b> – '
            'Smooth tailored fit.</p></li><li><p><b>Premium Fabric</b> – '
            'Wrinkle-free fabric.</p></li></ul>'
        )
        text = html_to_plain_text(raw)

        assert "<ul>" not in text
        assert "data-path-to-node" not in text
        assert text.splitlines() == [
            "Adjustable Waist – Smooth tailored fit.",
            "Premium Fabric – Wrinkle-free fabric.",
        ]

    def test_maps_explicit_kids_age_ranges(self):
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Toddler Embroidered Suit",
            "tags": ["Kids", "1-2Y", "3-4Y"],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")

        assert result is not None
        assert result.is_kids is True
        assert result.age_ranges_months == [(12, 35), (36, 59)]

    def test_map_basic_product(self):
        """Map a valid Shopify product."""
        product = map_shopify_to_product(
            SAMPLE_SHOPIFY_PRODUCT, "limelight", "limelight.pk"
        )
        assert product is not None
        assert product.id == "limelight:1234567890"
        assert "Red" in product.name or "Embroidered" in product.name
        assert product.price == 5000.0

    def test_product_url_generation(self):
        """Generate correct product URL."""
        product = map_shopify_to_product(
            SAMPLE_SHOPIFY_PRODUCT, "limelight", "limelight.pk"
        )
        assert product is not None
        assert "limelight.pk/products/red-embroidered-eid-dress" in product.product_url

    def test_missing_required_fields(self):
        """Return None for products missing required fields."""
        invalid_product = {"title": "No ID"}  # Missing id
        result = map_shopify_to_product(invalid_product, "brand", "domain.pk")
        assert result is None

    def test_skips_unit_sale_products(self):
        """Fabric sold by the meter (e.g. Nishat's real 'Meter' product_type,
        which has genuinely nonsensical fractional per-unit prices) is
        excluded — it's yardage, not a finished garment."""
        product = {**SAMPLE_SHOPIFY_PRODUCT, "product_type": "Meter"}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_skips_implausibly_priced_products(self):
        """A price below the plausibility floor (real observed case: Rs.
        9.20 for what should be a full-priced garment) is excluded rather
        than shown as a nonsensical near-free item."""
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "variants": [{"id": 1, "title": "Red / S", "price": "9.20"}],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_skips_products_with_no_image(self):
        """A product with no image at all (real observed case: Zellbury
        hand towels/dupattas with empty image arrays) is excluded — a
        blank card is useless in a visual shopping app."""
        product = {**SAMPLE_SHOPIFY_PRODUCT, "images": []}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_plausibly_priced_product_with_image_is_kept(self):
        """Sanity check: the exclusions above don't over-trigger on a
        normal, valid product."""
        result = map_shopify_to_product(SAMPLE_SHOPIFY_PRODUCT, "brand", "domain.pk")
        assert result is not None

    def test_skips_non_apparel_by_category(self):
        """Real observed case: Gul Ahmed's 'Ideas Home' cushion covers
        showed up in a wedding lehenga search — non-garment merchandise
        excluded by product_type."""
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Harmony T-200 Euro Sham Cushion Cover",
            "product_type": "Ideas Home",
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_skips_non_apparel_by_title_with_no_category(self):
        """Real observed case: Sana Safinaz sells a notebook with no
        product_type set at all — must catch this via title, not category."""
        product = {**SAMPLE_SHOPIFY_PRODUCT, "title": "Inky Bloom Notebook", "product_type": ""}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_skips_perfume_and_jewelry(self):
        for title in ["P-Statesman Perfume", "Toggle Lock Bracelet", "Vintage Ring Set"]:
            product = {**SAMPLE_SHOPIFY_PRODUCT, "title": title, "product_type": ""}
            result = map_shopify_to_product(product, "brand", "domain.pk")
            assert result is None, f"Expected {title!r} to be excluded as non-apparel"

    def test_skips_non_apparel_plural_category(self):
        # Regression: switching to whole-word matching (to stop "polo"
        # matching inside "apology") initially broke plural forms — a
        # real observed case, Outfitters' "FRAGRANCES" category, stopped
        # being excluded because the keyword list only had "fragrance".
        product = {**SAMPLE_SHOPIFY_PRODUCT, "title": "Verde", "product_type": "FRAGRANCES"}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_skips_footwear(self):
        # Real observed case: Outfitters' "Closed Shoes" category showing
        # up in what should be a clothing-only catalog.
        product = {**SAMPLE_SHOPIFY_PRODUCT, "title": "Canvas Slip-On", "product_type": "Closed Shoes"}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_extension_can_opt_in_to_footwear(self):
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Canvas Slip-On",
            "product_type": "Closed Shoes",
        }
        result = map_shopify_to_product(
            product,
            "brand",
            "domain.pk",
            allow_footwear=True,
        )
        assert result is not None
        assert result.category == "Closed Shoes"

    def test_skips_mehndi_stencils_from_apparel_catalog(self):
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Reusable Mehndi Stencil Set",
            "product_type": "Accessories",
        }
        assert map_shopify_to_product(product, "brand", "domain.pk") is None

    def test_tags_kids_apparel_by_title(self):
        # Real observed case: Gul Ahmed's "Toddler Boy Multi Sweatshirt"
        # and "Junior Boy Clay Printed Sweatshirt" surfaced in a plain
        # adult "sweatshirt" search — kids items are kept (Dhaaga does
        # carry them) but tagged so search can filter them appropriately
        # rather than mixing them into an adult's search by default.
        for title in ["Toddler Boy Multi Sweatshirt", "Junior Boy Clay Printed Sweatshirt"]:
            product = {**SAMPLE_SHOPIFY_PRODUCT, "title": title, "product_type": ""}
            result = map_shopify_to_product(product, "brand", "domain.pk")
            assert result is not None, f"Expected {title!r} to still be kept, just tagged"
            assert result.is_kids is True

    def test_tags_kids_apparel_by_category_prefix(self):
        # Real observed case: Beechtree's kids line uses its own category
        # prefix ("BTK-East" / "BTK-West") with no kids keyword in the
        # title at all.
        product = {**SAMPLE_SHOPIFY_PRODUCT, "title": "2 Piece Floral Set", "product_type": "BTK-East"}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is not None
        assert result.is_kids is True

    def test_tags_kids_apparel_by_shopify_tags(self):
        # Real observed case: Beechtree's "2 PIECE EMBROIDERED SUIT" has no
        # kids keyword in title or product_type at all — only its Shopify
        # tags ("Kids", "Little Girls", "child") reveal it's a kids item.
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "2 Piece Embroidered Suit",
            "product_type": "",
            "tags": ["1-2Y", "child", "Kid-FUS", "Kids", "Little Girls", "NA-West"],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is not None
        assert result.is_kids is True

    def test_skips_non_apparel_by_shopify_tags(self):
        # Real observed case: Alkaram's "VELVET DUSK" has a generic title
        # with no obvious perfume keyword — only its tags ("Fragrance",
        # "MISTS") reveal it's not a garment.
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Velvet Dusk",
            "product_type": "",
            "tags": ["Female", "Fragrance", "MISTS", "uploaded-11-march-26"],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_keeps_product_with_unrelated_shopify_tags(self):
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Embroidered Lawn Kurta",
            "product_type": "Kurta",
            "tags": ["Women", "Summer-26", "New In", "Embroidered"],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is not None
        assert result.shopify_tags == ["Women", "Summer-26", "New In", "Embroidered"]
        assert result.department == "women"

    def test_tags_kids_apparel_by_vendor(self):
        # Real observed case: Zellbury and Outfitters use `vendor` as a
        # per-product department/age label ("ZELLBURY GIRLS", "Boys
        # Junior") independent of the brand-level department, with no
        # kids signal anywhere in the title, category, or tags.
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "title": "Printed Shirt",
            "product_type": "Shirts",
            "vendor": "ZELLBURY GIRLS",
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is not None
        assert result.is_kids is True

    def test_skips_fully_out_of_stock_product(self):
        # Real observed case: a large fraction of the cached catalog was
        # completely sold out (every variant unavailable) but still
        # shown as if purchasable, since availability was never checked.
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "variants": [
                {"id": 1, "title": "Red / S", "price": "5000", "available": False},
                {"id": 2, "title": "Blue / M", "price": "5000", "available": False},
            ],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is None

    def test_keeps_product_with_at_least_one_available_variant(self):
        product = {
            **SAMPLE_SHOPIFY_PRODUCT,
            "variants": [
                {"id": 1, "title": "Red / S", "price": "5000", "available": False},
                {"id": 2, "title": "Blue / M", "price": "5000", "available": True},
            ],
        }
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is not None

    def test_does_not_flag_boyfriend_fit_as_kids(self):
        # Regression: whole-word matching must not treat "boy" inside
        # "boyfriend" (a legitimate unisex jeans-fit term) as a kids signal.
        product = {**SAMPLE_SHOPIFY_PRODUCT, "title": "Boyfriend Fit Jeans", "product_type": "Bottoms"}
        result = map_shopify_to_product(product, "brand", "domain.pk")
        assert result is not None
        assert result.is_kids is False


class TestKeywordMatching:
    """Test occasion and tag extraction."""

    def test_extract_occasion_eid(self):
        """Detect Eid occasion from product description."""
        product = Product(
            id="test:1",
            name="Eid Dress",
            description="Perfect for Eid celebrations",
            price=5000,
            colors=["Red"],
            sizes=["M"],
            occasion="",
            tags=[],
            image="",
            secondaryImage=None,
            product_url="",
        )
        occasion = extract_occasion(product)
        assert occasion == "eid"

    def test_extract_occasion_wedding(self):
        """Detect wedding occasion."""
        product = Product(
            id="test:1",
            name="Bridal Wedding Dress",
            description="Beautiful bridal dress for your wedding",
            price=50000,
            colors=["White"],
            sizes=["S"],
            occasion="",
            tags=[],
            image="",
            secondaryImage=None,
            product_url="",
        )
        occasion = extract_occasion(product)
        assert occasion == "baraat"

    def test_lehenga_category_is_classified_as_wedding(self):
        product = Product(
            id="test:lehenga",
            name="Embroidered Look 12",
            category="Lehenga",
            description="",
            price=50000,
            image="",
            product_url="",
        )
        assert extract_occasion(product) == "wedding"

    def test_extract_tags_material(self):
        """Extract material tags."""
        product = Product(
            id="test:1",
            name="Cotton Dress",
            description="100% pure cotton with embroidery",
            price=5000,
            colors=["Blue"],
            sizes=["M"],
            occasion="casual",
            tags=[],
            image="",
            secondaryImage=None,
            product_url="",
        )
        tags = extract_tags(product)
        assert "cotton" in tags
        assert "embroidered" in tags

    def test_tag_product_complete(self):
        """Complete tagging of a product."""
        product = Product(
            id="test:1",
            name="Formal Black Silk Dress",
            description="Elegant silk dress for formal occasions",
            price=15000,
            colors=["Black", "White"],
            sizes=["XS", "S", "M"],
            occasion="",
            tags=[],
            image="",
            secondaryImage=None,
            product_url="",
        )
        tagged = tag_product(product)
        assert tagged.occasion != ""
        assert len(tagged.tags) > 0
