"""Product search service with keyword scoring and filtering."""

import logging
import re
from typing import Any

from app.schemas.product import Product, ProductSearchResponse

logger = logging.getLogger(__name__)

# Match weights relative to a title match (1.0). category is Shopify's own
# product_type — a precise merchant-set garment label, as trustworthy as the
# title. shopify_tags are merchant-set too but noisier (mixed in with SKU
# codes, sale campaign tags, size charts), so weighted a bit below title/
# category. description is raw scraped HTML full of generic boilerplate
# (fabric/wash-care copy) that incidentally mentions unrelated style words,
# so a hit there is the weakest signal.
CATEGORY_MATCH_WEIGHT = 1.0
SHOPIFY_TAGS_MATCH_WEIGHT = 0.75
DESCRIPTION_MATCH_WEIGHT = 0.25


def _contains_word(keyword: str, text: str) -> bool:
    """Whole-word match, tolerant of a simple trailing plural "s" — plain
    substring matching lets e.g. "polo" match inside "apology", surfacing
    completely unrelated products; strict `\\bword\\b` then misses a
    shopper searching "polos" against a title that says "Polo"."""
    return re.search(rf"\b{re.escape(keyword)}s?\b", text) is not None


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
    """Rank by relevance tier, diversifying by brand only *within* each
    tier — products that scored 0 ("filler") are never included at all.

    Real bug this fixes: round-robining across ALL brands regardless of
    score meant a brand with zero keyword matches for e.g. "lehenga" still
    contributed its top-priced item into the very first round, surfacing
    completely unrelated products (a hand towel) ahead of or alongside
    actual matches.

    Second real bug this fixes: when literally nothing matched (e.g.
    "sherwani" — a category none of the registered brands carry), this
    used to append the *entire* catalog as filler — surfacing e.g. socks
    and hair ties for a sherwani search, dressed up to look like matches.

    Third real bug this fixes, found via a real "korean pant" search: even
    with real matches present, this still appended the entire *rest* of
    the catalog as filler after them — a query with ~15 genuine matches
    reported a total of 4197 (the full catalog size), and a shopper
    scrolling past the real matches on page 2+ would hit pure noise. A
    free-text query should only ever return what it actually matched, at
    any count — never pad out to "the whole catalog, reshuffled."
    """
    relevant = [(p, s) for p, s in scored if s > 0]

    # Sub-tier the relevant matches by exact score so a perfect match still
    # outranks a partial one, diversifying by brand within each score level.
    score_levels = sorted({s for _, s in relevant}, reverse=True)
    ranked: list[Product] = []
    for level in score_levels:
        tier = [(p, s) for p, s in relevant if s == level]
        ranked.extend(_round_robin_by_brand(tier))

    return ranked


def _keyword_score(product: Product, keywords: list[str]) -> float:
    """Calculate keyword match score for a product.

    Each keyword is checked against title, category (Shopify product_type),
    shopify_tags, and description, in that order of trust — a keyword
    scores whichever field's weight is highest it matched in, not the sum
    across fields. Title/category are precise merchant-set labels; tags
    are merchant-set but noisier; descriptions are raw scraped HTML full
    of generic boilerplate that mentions unrelated style words across
    unrelated garment types — weighting them lowest keeps e.g. a
    "knitted" camisole from ranking alongside actual knitted polos.

    Args:
        product: Product to score
        keywords: List of search keywords

    Returns:
        Score between 0 and 1 (1 = every keyword matched in title/category)
    """
    if not keywords:
        return 1.0

    name = product.name.lower()
    category = (product.category or "").lower()
    tags_text = " ".join(product.shopify_tags).lower()
    description = product.description.lower()

    score = 0.0
    for kw in keywords:
        kw_lower = kw.lower()
        if _contains_word(kw_lower, name) or _contains_word(kw_lower, category):
            score += CATEGORY_MATCH_WEIGHT
        elif _contains_word(kw_lower, tags_text):
            score += SHOPIFY_TAGS_MATCH_WEIGHT
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
