"""Recommendation service for product alternatives using tag-based matching."""

import logging
from typing import Any

from app.schemas.product import Product, ProductSearchResponse

logger = logging.getLogger(__name__)


def _tag_similarity(tags1: list[str], tags2: list[str]) -> float:
    """Calculate tag-based similarity between two products.
    
    Args:
        tags1: Tags from product 1
        tags2: Tags from product 2
        
    Returns:
        Similarity score between 0 and 1
    """
    if not tags1 or not tags2:
        return 0.0

    set1 = set(t.lower() for t in tags1)
    set2 = set(t.lower() for t in tags2)

    # Jaccard similarity: intersection / union
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0


def _color_similarity(colors1: list[str], colors2: list[str]) -> float:
    """Calculate color similarity (color family matching).
    
    Args:
        colors1: Colors from product 1
        colors2: Colors from product 2
        
    Returns:
        Similarity score between 0 and 1
    """
    if not colors1 or not colors2:
        return 0.0

    # Simple check: any color overlap?
    set1 = set(c.lower() for c in colors1)
    set2 = set(c.lower() for c in colors2)

    if set1 & set2:  # Same colors
        return 1.0
    return 0.2  # Different colors get slight bonus for variety


def _size_compatibility(sizes1: list[str], sizes2: list[str]) -> float:
    """Calculate size range compatibility.
    
    Args:
        sizes1: Sizes from product 1
        sizes2: Sizes from product 2
        
    Returns:
        Compatibility score (1.0 if any overlap)
    """
    if not sizes1 or not sizes2:
        return 0.5  # Neutral if one has "One Size"

    set1 = set(s.lower() for s in sizes1)
    set2 = set(s.lower() for s in sizes2)

    return 1.0 if set1 & set2 else 0.5


def _combined_similarity(
    product: Product,
    reference: Product,
    tag_weight: float = 0.5,
    color_weight: float = 0.25,
    price_weight: float = 0.15,
    size_weight: float = 0.1,
) -> float:
    """Calculate combined similarity score.
    
    Args:
        product: Product to score
        reference: Reference product
        tag_weight: Weight for tag similarity (0-1)
        color_weight: Weight for color similarity
        price_weight: Weight for price similarity
        size_weight: Weight for size compatibility
        
    Returns:
        Combined score between 0 and 1
    """
    tag_sim = _tag_similarity(product.tags, reference.tags)
    color_sim = _color_similarity(product.colors, reference.colors)
    size_compat = _size_compatibility(product.sizes, reference.sizes)

    # Price similarity: exponential decay (closer = higher)
    price_diff = abs(product.price - reference.price)
    price_sim = 1.0 / (1.0 + (price_diff / 10000.0))  # Max penalty at +/- 10k

    combined = (
        tag_sim * tag_weight
        + color_sim * color_weight
        + size_compat * size_weight
        + price_sim * price_weight
    )

    return combined


class AlternativesService:
    """Product recommendations using tag-based similarity."""

    @staticmethod
    def get_alternatives(
        reference_product: Product,
        candidates: list[Product],
        exclude_same_brand: bool = False,
        limit: int = 10,
    ) -> list[Product]:
        """Find similar products for a given product.
        
        Args:
            reference_product: Product to find alternatives for
            candidates: Pool of candidate products
            exclude_same_brand: Exclude products from same brand
            limit: Maximum results to return
            
        Returns:
            List of similar products sorted by similarity (highest first)
        """
        # Filter out the reference product itself
        filtered = [
            p for p in candidates
            if p.id != reference_product.id
        ]

        # Optionally exclude same brand
        if exclude_same_brand:
            ref_brand = reference_product.id.split(":")[0]
            filtered = [
                p for p in filtered
                if not p.id.startswith(f"{ref_brand}:")
            ]

        # Score similarity
        scored = [
            (product, _combined_similarity(product, reference_product))
            for product in filtered
        ]

        # Sort by similarity (highest first)
        scored.sort(key=lambda x: -x[1])

        # Return top N
        return [p for p, _ in scored[:limit]]

    @staticmethod
    def get_alternatives_response(
        reference_product: Product,
        candidates: list[Product],
        exclude_same_brand: bool = False,
        limit: int = 10,
        page: int = 1,
        page_size: int = 20,
    ) -> ProductSearchResponse:
        """Get alternatives with pagination.
        
        Args:
            reference_product: Product to find alternatives for
            candidates: Pool of candidate products
            exclude_same_brand: Exclude same brand products
            limit: Maximum alternatives to consider
            page: Page number
            page_size: Results per page
            
        Returns:
            Paginated ProductSearchResponse
        """
        alternatives = AlternativesService.get_alternatives(
            reference_product,
            candidates,
            exclude_same_brand=exclude_same_brand,
            limit=limit,
        )

        total = len(alternatives)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated = alternatives[start_idx:end_idx]

        return ProductSearchResponse(
            items=paginated,
            total=total,
            page=page,
            page_size=page_size,
            has_more=end_idx < total,
        )
