"""Tests for Shopify mapper and keyword tagger."""

import pytest

from app.nlp.keyword_matcher import extract_occasion, extract_tags, tag_product
from app.schemas.product import Product
from app.shopify.mapper import extract_colors, extract_sizes, map_shopify_to_product


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


class TestMapperBasic:
    """Test basic Shopify to Product mapping."""

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
        assert occasion == "wedding"

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
