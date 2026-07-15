"""Product search service with keyword scoring and filtering."""

import logging
import re
from typing import Any

from app.schemas.product import Product, ProductSearchResponse

logger = logging.getLogger(__name__)

# Description-only match weight relative to a title match. Descriptions are
# raw scraped HTML full of generic boilerplate (fabric/wash-care copy) that
# incidentally mentions unrelated style words, so a hit there is a much
# weaker relevance signal than the same word appearing in the product title.
DESCRIPTION_MATCH_WEIGHT = 0.25


def _contains_word(keyword: str, text: str) -> bool:
    """Whole-word match — plain substring matching lets e.g. "polo" match
    inside "apology", surfacing completely unrelated products."""
    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


def _brand_slug(product: Product) -> str:
    return product.id.split(":", 1)[0]


def _round_robin_by_brand(scored: list[tuple[Product, float]]) -> list[Product]:
    """Interleave a single relevance tier across brands round-robin.

    A flat sort that falls back to product name on tied scores (the common
    case within one tier, where every product in it shares the same score)
    clusters results by whichever brand's naming convention happens to sort
    first alphabetically — e.g. many brands name products "2 PIECE ... SUIT",
    so one brand's catalog can dominate every result. Grouping by brand
    (sorted by price within each brand) and round-robining across groups
    guarantees real brand variety within this tier.
    """
    groups: dict[str, list[tuple[Product, float]]] = {}
    for product, score in scored:
        groups.setdefault(_brand_slug(product), []).append((product, score))

    for group in groups.values():
        group.sort(key=lambda x: x[0].price)

    brand_order = sorted(groups.keys())
    result: list[Product] = []
    round_idx = 0
    while any(round_idx < len(groups[slug]) for slug in brand_order):
        for slug in brand_order:
            if round_idx < len(groups[slug]):
                result.append(groups[slug][round_idx][0])
        round_idx += 1

    return result


def _diversify_by_brand(scored: list[tuple[Product, float]]) -> list[Product]:
    """Rank by relevance tier first, diversifying by brand only *within*
    each tier — never interleaving irrelevant filler ahead of or alongside
    genuine matches.

    Real bug this fixes: round-robining across ALL brands regardless of
    score meant a brand with zero keyword matches for e.g. "lehenga" still
    contributed its top-priced item into the very first round, surfacing
    completely unrelated products (a hand towel) ahead of or alongside
    actual matches. Tiering by score first — relevant (>0) before filler
    (0) — guarantees relevance always wins; diversification only decides
    ordering *within* a tier of equally-relevant items.

    Second real bug this fixes: a free-text query that matches nothing at
    all in the current catalog (e.g. "sherwani" — a category none of the
    24 registered brands carry) scored every product 0, so this used to
    append the *entire* catalog as "filler" — surfacing e.g. socks and
    hair ties for a sherwani search, dressed up to look like real matches.
    When there isn't a single relevant match for an actual keyword query,
    the honest result is zero results, not the whole catalog reshuffled.
    """
    relevant = [(p, s) for p, s in scored if s > 0]
    filler = [(p, s) for p, s in scored if s <= 0]

    # Sub-tier the relevant matches by exact score so a perfect match still
    # outranks a partial one, diversifying by brand within each score level.
    score_levels = sorted({s for _, s in relevant}, reverse=True)
    ranked: list[Product] = []
    for level in score_levels:
        tier = [(p, s) for p, s in relevant if s == level]
        ranked.extend(_round_robin_by_brand(tier))

    if relevant:
        ranked.extend(_round_robin_by_brand(filler))
    return ranked


def _keyword_score(product: Product, keywords: list[str]) -> float:
    """Calculate keyword match score for a product.

    A whole-word match in the product title scores a full point; a match
    found only in the description scores a fraction of a point. Titles
    reliably state the garment type ("Polo", "Camisole", "Kurta"), while
    descriptions are noisy scraped HTML that mentions fabric/style words
    across unrelated garment types — weighting title matches higher keeps
    e.g. a "knitted" camisole from ranking alongside actual knitted polos.

    Args:
        product: Product to score
        keywords: List of search keywords

    Returns:
        Score between 0 and 1 (1 = every keyword matched in the title)
    """
    if not keywords:
        return 1.0

    name = product.name.lower()
    description = product.description.lower()

    score = 0.0
    for kw in keywords:
        kw_lower = kw.lower()
        if _contains_word(kw_lower, name):
            score += 1.0
        elif _contains_word(kw_lower, description):
            score += DESCRIPTION_MATCH_WEIGHT

    return score / len(keywords)


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

        # Diversify across brands rather than a flat score/name sort (see
        # _diversify_by_brand — a flat sort clusters results by whichever
        # brand's product-naming convention wins ties alphabetically).
        ranked_products = _diversify_by_brand(scored)

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
