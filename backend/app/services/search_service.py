"""Product search service with keyword scoring and filtering."""

import logging
from typing import Any

from app.schemas.product import Product, ProductSearchResponse

logger = logging.getLogger(__name__)


def _keyword_score(product: Product, keywords: list[str]) -> float:
    """Calculate keyword match score for a product.
    
    Args:
        product: Product to score
        keywords: List of search keywords
        
    Returns:
        Score between 0 and 1 (1 = perfect match)
    """
    if not keywords:
        return 1.0

    text = f"{product.name} {product.description}".lower()
    matches = sum(1 for kw in keywords if kw.lower() in text)
    return matches / len(keywords)


def _apply_filters(
    products: list[Product],
    occasion: str | None = None,
    color: str | None = None,
    size: str | None = None,
    tags: list[str] | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
) -> list[Product]:
    """Apply structured filters to products.
    
    Args:
        products: Products to filter
        occasion: Filter by occasion (e.g., 'eid', 'wedding')
        color: Filter by color (partial match)
        size: Filter by size (exact match)
        tags: Filter by tags (product must have all tags)
        max_price: Maximum price
        min_price: Minimum price
        
    Returns:
        Filtered products list
    """
    filtered = products

    if occasion:
        filtered = [p for p in filtered if p.occasion == occasion.lower()]

    if color:
        color_lower = color.lower()
        filtered = [
            p for p in filtered
            if any(color_lower in c.lower() for c in p.colors)
        ]

    if size:
        filtered = [p for p in filtered if size in p.sizes]

    if tags:
        tags_lower = [t.lower() for t in tags]
        filtered = [
            p for p in filtered
            if all(any(tag in pt.lower() for pt in p.tags) for tag in tags_lower)
        ]

    if min_price is not None:
        filtered = [p for p in filtered if p.price >= min_price]

    if max_price is not None:
        filtered = [p for p in filtered if p.price <= max_price]

    return filtered


class SearchService:
    """Product search with keyword scoring and filtering."""

    @staticmethod
    def search(
        products: list[Product],
        query: str = "",
        occasion: str | None = None,
        color: str | None = None,
        size: str | None = None,
        tags: list[str] | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ProductSearchResponse:
        """Search products with keyword scoring and filters.
        
        Args:
            products: Candidate products (from cache)
            query: Free-text search query
            occasion: Filter by occasion
            color: Filter by color
            size: Filter by size
            tags: Filter by tags (all must match)
            max_price: Maximum price
            min_price: Minimum price
            page: Page number (1-indexed)
            page_size: Results per page
            
        Returns:
            Paginated ProductSearchResponse with scored results
        """
        # Parse keywords from query
        keywords = [kw.strip() for kw in query.split() if kw.strip()]

        # Apply filters
        filtered = _apply_filters(
            products,
            occasion=occasion,
            color=color,
            size=size,
            tags=tags,
            max_price=max_price,
            min_price=min_price,
        )

        # Score by keyword matches
        scored = [
            (product, _keyword_score(product, keywords))
            for product in filtered
        ]

        # Sort by score (highest first), then by name for tie-breaking
        scored.sort(key=lambda x: (-x[1], x[0].name))

        # Extract products (discard scores)
        ranked_products = [p for p, _ in scored]

        # Paginate
        total = len(ranked_products)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = ranked_products[start_idx:end_idx]

        return ProductSearchResponse(
            items=paginated,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end_idx < total,
        )

    @staticmethod
    def search_by_brands(
        products: list[Product],
        brand_slugs: list[str],
        page: int = 1,
        page_size: int = 20,
    ) -> ProductSearchResponse:
        """Filter products by brand slugs.
        
        Args:
            products: Candidate products
            brand_slugs: List of brand slugs to include
            page: Page number
            page_size: Results per page
            
        Returns:
            Paginated results filtered by brand
        """
        filtered = [
            p for p in products
            if any(p.id.startswith(f"{slug}:") for slug in brand_slugs)
        ]

        total = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = filtered[start_idx:end_idx]

        return ProductSearchResponse(
            items=paginated,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end_idx < total,
        )
