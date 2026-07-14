"""Unit tests for Phase 3 services — search, alternatives, collections."""

import pytest

from app.schemas.product import Product
from app.services.search_service import SearchService, _keyword_score, _apply_filters
from app.services.alternatives_service import (
    AlternativesService,
    _tag_similarity,
    _color_similarity,
)


@pytest.fixture
def sample_products() -> list[Product]:
    """Create sample products for testing."""
    return [
        Product(
            id="limelight:1",
            name="Red Eid Dress",
            description="Beautiful red cotton dress perfect for Eid",
            price=5000.0,
            colors=["Red"],
            sizes=["S", "M", "L"],
            occasion="eid",
            tags=["cotton", "traditional"],
            image="https://example.com/1.jpg",
            secondaryImage=None,
            product_url="https://limelight.pk/products/1",
        ),
        Product(
            id="alkaram:1",
            name="Blue Formal Suit",
            description="Elegant blue silk suit for formal occasions",
            price=15000.0,
            colors=["Blue"],
            sizes=["M", "L", "XL"],
            occasion="formal",
            tags=["silk", "modern"],
            image="https://example.com/2.jpg",
            secondaryImage=None,
            product_url="https://alkaram.pk/products/1",
        ),
        Product(
            id="limelight:2",
            name="Cotton Casual Shirt",
            description="Comfortable cotton shirt for everyday wear",
            price=2000.0,
            colors=["White", "Blue"],
            sizes=["S", "M", "L", "XL"],
            occasion="casual",
            tags=["cotton", "modern"],
            image="https://example.com/3.jpg",
            secondaryImage=None,
            product_url="https://limelight.pk/products/2",
        ),
        Product(
            id="sana-safinaz:1",
            name="Embroidered Wedding Dress",
            description="Stunning embroidered bridal dress for wedding",
            price=50000.0,
            colors=["Red", "Gold"],
            sizes=["XS", "S", "M"],
            occasion="wedding",
            tags=["embroidered", "traditional"],
            image="https://example.com/4.jpg",
            secondaryImage=None,
            product_url="https://sana.pk/products/1",
        ),
        Product(
            id="gul-ahmed:1",
            name="Red Cotton Mehndi Suit",
            description="Beautiful red cotton suit for mehndi celebration",
            price=8000.0,
            colors=["Red"],
            sizes=["S", "M", "L"],
            occasion="mehndi",
            tags=["cotton", "embroidered"],
            image="https://example.com/5.jpg",
            secondaryImage=None,
            product_url="https://gul.pk/products/1",
        ),
    ]


class TestKeywordScoring:
    """Test keyword-based product scoring."""

    def test_exact_keyword_match(self, sample_products):
        """Score products by exact keyword match."""
        product = sample_products[0]  # "Red Eid Dress"
        keywords = ["eid", "red"]
        score = _keyword_score(product, keywords)
        assert score == 1.0  # Both keywords found

    def test_partial_keyword_match(self, sample_products):
        """Score products by partial keyword match."""
        product = sample_products[0]
        keywords = ["eid", "blue", "silk"]
        score = _keyword_score(product, keywords)
        assert 0 < score < 1.0  # Only "eid" matches

    def test_no_keywords(self, sample_products):
        """Return full score for empty keywords."""
        product = sample_products[0]
        score = _keyword_score(product, [])
        assert score == 1.0


class TestFiltering:
    """Test filter application."""

    def test_filter_by_occasion(self, sample_products):
        """Filter products by occasion."""
        filtered = _apply_filters(sample_products, occasion="eid")
        assert len(filtered) == 1
        assert filtered[0].id == "limelight:1"

    def test_filter_by_color(self, sample_products):
        """Filter products by color."""
        filtered = _apply_filters(sample_products, color="red")
        assert len(filtered) == 3  # Products with red
        assert all("red" in p.colors[0].lower() or "red" in str(p.colors).lower() for p in filtered)

    def test_filter_by_size(self, sample_products):
        """Filter products by size."""
        # "M" matches all 5 fixtures, so it wouldn't catch a no-op filter bug —
        # "XL" only matches alkaram:1 and limelight:2, which actually discriminates.
        filtered = _apply_filters(sample_products, size="XL")
        assert len(filtered) == 2
        assert {p.id for p in filtered} == {"alkaram:1", "limelight:2"}

    def test_filter_by_tags(self, sample_products):
        """Filter products by tags (all must match)."""
        filtered = _apply_filters(sample_products, tags=["cotton"])
        assert len(filtered) == 3  # Cotton products

    def test_filter_by_price_range(self, sample_products):
        """Filter products by price range."""
        filtered = _apply_filters(sample_products, min_price=3000, max_price=10000)
        # Only limelight:1 (5000) and gul-ahmed:1 (8000) fall in [3000, 10000]
        assert len(filtered) == 2
        assert {p.id for p in filtered} == {"limelight:1", "gul-ahmed:1"}


class TestSearchService:
    """Test product search functionality."""

    def test_search_by_keyword(self, sample_products):
        """Search products by keyword."""
        result = SearchService.search(
            sample_products, query="eid red cotton", page=1, page_size=10
        )
        assert result.total >= 1
        assert result.page == 1
        # Should include red eid dress
        assert any("eid" in p.name.lower() for p in result.items)

    def test_search_with_occasion_filter(self, sample_products):
        """Search with occasion filter."""
        result = SearchService.search(
            sample_products, query="dress", occasion="wedding", page=1, page_size=10
        )
        assert result.total >= 1
        assert all(p.occasion == "wedding" for p in result.items)

    def test_search_pagination(self, sample_products):
        """Test pagination in search results."""
        result = SearchService.search(
            sample_products, page=1, page_size=2
        )
        assert len(result.items) <= 2
        assert result.has_more == (result.total > 2)

    def test_search_by_brands(self, sample_products):
        """Filter products by brand slugs."""
        result = SearchService.search_by_brands(
            sample_products,
            brand_slugs=["limelight"],
            page=1,
            page_size=10,
        )
        assert all("limelight:" in p.id for p in result.items)


class TestTagSimilarity:
    """Test tag-based similarity."""

    def test_identical_tags(self):
        """Identical tags have 1.0 similarity."""
        tags1 = ["cotton", "traditional"]
        tags2 = ["cotton", "traditional"]
        score = _tag_similarity(tags1, tags2)
        assert score == 1.0

    def test_partial_tag_overlap(self):
        """Partial tag overlap."""
        tags1 = ["cotton", "traditional", "embroidered"]
        tags2 = ["cotton", "modern"]
        score = _tag_similarity(tags1, tags2)
        assert 0 < score < 1.0

    def test_no_tag_overlap(self):
        """No tag overlap."""
        tags1 = ["cotton"]
        tags2 = ["silk"]
        score = _tag_similarity(tags1, tags2)
        assert score == 0.0

    def test_empty_tags(self):
        """Empty tags return 0."""
        score = _tag_similarity([], ["cotton"])
        assert score == 0.0


class TestColorSimilarity:
    """Test color-based similarity."""

    def test_same_colors(self):
        """Same colors have 1.0 similarity."""
        colors1 = ["Red"]
        colors2 = ["Red"]
        score = _color_similarity(colors1, colors2)
        assert score == 1.0

    def test_different_colors(self):
        """Different colors have 0.2 penalty."""
        colors1 = ["Red"]
        colors2 = ["Blue"]
        score = _color_similarity(colors1, colors2)
        assert score == 0.2

    def test_overlapping_colors(self):
        """Overlapping colors have 1.0 similarity."""
        colors1 = ["Red", "Blue"]
        colors2 = ["Blue", "Green"]
        score = _color_similarity(colors1, colors2)
        assert score == 1.0


class TestAlternativesService:
    """Test alternatives/recommendations."""

    def test_get_alternatives(self, sample_products):
        """Get similar products."""
        reference = sample_products[0]  # Red Eid Dress
        alternatives = AlternativesService.get_alternatives(
            reference, sample_products, limit=5
        )
        # Should not include the reference product itself
        assert reference.id not in [p.id for p in alternatives]
        # Should return up to limit
        assert len(alternatives) <= 5

    def test_exclude_same_brand(self, sample_products):
        """Exclude products from same brand."""
        reference = sample_products[0]  # limelight:1
        alternatives = AlternativesService.get_alternatives(
            reference,
            sample_products,
            exclude_same_brand=True,
            limit=5,
        )
        # Should not include other limelight products
        assert all(not p.id.startswith("limelight:") for p in alternatives)

    def test_high_similarity_ranking(self, sample_products):
        """Similar products rank higher."""
        reference = sample_products[0]  # Red cotton eid dress
        alternatives = AlternativesService.get_alternatives(
            reference, sample_products, limit=5
        )
        if len(alternatives) > 0:
            # First alternative should have similar tags/occasion
            first = alternatives[0]
            assert first.occasion in ["eid", "casual", "mehndi"]  # Same tradition
