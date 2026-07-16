"""Product search service with keyword scoring and filtering."""

import logging
import re
from typing import Any

from app.kids_age import product_supports_age
from app.nlp.pakistani_events import event_match_score
from app.nlp.colors import matching_color
from app.nlp.apparel_classification import FORMAL_FABRICS, matches_classification
from app.nlp.garments import (
    extract_garment_descriptors,
    extract_primary_garment,
    matches_garment_text,
)
from app.nlp.product_semantics import ensure_product_semantics
from app.schemas.product import Product, ProductSearchResponse
from app.shopify.mapper import is_non_apparel_listing

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
# Semantic profiles are valuable for focused vibe searches, but enriching
# several thousand broad occasion matches on demand makes a one-word audience
# confirmation take minutes. Structured filters have already established
# correctness at this point, so broad sets use the cheaper keyword/occasion
# ranking and retain semantic reranking for focused candidate pools.
SEMANTIC_SCORING_MAX_CANDIDATES = 1000
EVENT_SCORE_CACHE_MAX_ENTRIES = 100_000
_event_score_cache: dict[tuple[str, str], tuple[int, float]] = {}

QUERY_ALIASES: dict[str, list[str]] = {
    "daaku": ["kurta", "waistcoat", "shawl", "shalwar"],
    "daku": ["kurta", "waistcoat", "shawl", "shalwar"],
    "bandit": ["kurta", "waistcoat", "shawl", "shalwar"],
}
GENERIC_QUERY_WORDS = {
    "a", "an", "the", "for", "to", "like", "me", "my", "day",
    "outfit", "outfits", "clothes", "clothing", "wear", "formal", "casual",
    "semi", "eastern", "western", "gym", "workout", "exercise", "activewear",
    "sportswear", "athleisure", "semi-formal", "semiformal", "party", "occasion",
    "bridal", "fusion", "desi", "ethnic", "daily", "everyday",
}
SEMANTIC_STOP_WORDS = GENERIC_QUERY_WORDS | {
    "show", "find", "need", "want", "looking", "please", "some", "something",
    "this", "that", "with", "from", "under", "less", "than", "woman", "man",
}

_CATEGORY_CHILDREN: dict[str, set[str]] = {
    "top": {"peplum top", "crop top", "tank top", "blouse", "tunic"},
    "dress": {"shirt dress", "wrap dress", "cocktail dress", "slip dress", "maxi", "gown"},
    "trousers": {"cigarette pants", "palazzo"},
}


def _contains_word(keyword: str, text: str) -> bool:
    """Whole-word match, tolerant of a simple trailing plural "s" — plain
    substring matching lets e.g. "polo" match inside "apology", surfacing
    completely unrelated products; strict `\\bword\\b` then misses a
    shopper searching "polos" against a title that says "Polo"."""
    if keyword in {"stripe", "stripes", "striped"}:
        return re.search(r"\bstrip(?:e|ed|es|ing)\b", text) is not None
    stem = keyword[:-1] if keyword.endswith("s") and not keyword.endswith("ss") else keyword
    return re.search(rf"\b{re.escape(stem)}s?\b", text) is not None


def _brand_slug(product: Product) -> str:
    return product.id.split(":", 1)[0]


def _cached_event_match_score(product: Product, occasion: str) -> float:
    """Cache event suitability for an immutable catalog snapshot.

    Follow-up filters repeatedly evaluate the same cached Shopify products.
    The fingerprint invalidates an entry if a refresh changes any evidence
    used by ``event_match_score`` while the compact id/event key keeps memory
    bounded instead of retaining full descriptions in cache keys.
    """
    fingerprint = hash((
        product.name,
        product.category,
        product.description,
        product.occasion,
        tuple(product.shopify_tags),
        tuple(product.tags),
        tuple(product.colors),
    ))
    key = (product.id, occasion.lower())
    cached = _event_score_cache.get(key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    score = event_match_score(product, occasion)
    if len(_event_score_cache) >= EVENT_SCORE_CACHE_MAX_ENTRIES:
        _event_score_cache.clear()
    _event_score_cache[key] = (fingerprint, score)
    return score


def _normalized_size(value: str) -> str:
    compact = re.sub(r"[^A-Z0-9]+", "", value.upper())
    return {
        "EXTRASMALL": "XS",
        "SMALL": "S",
        "MEDIUM": "M",
        "LARGE": "L",
        "EXTRALARGE": "XL",
        "2XL": "XXL",
        "XXLARGE": "XXL",
    }.get(compact, compact)


def _round_robin_by_brand(
    scored: list[tuple[Product, float]], limit: int | None = None
) -> list[Product]:
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
                if limit is not None and len(result) >= limit:
                    return result
        round_idx += 1

    return result


def _diversify_by_brand(
    scored: list[tuple[Product, float]], limit: int | None = None
) -> list[Product]:
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
        remaining = None if limit is None else limit - len(ranked)
        if remaining is not None and remaining <= 0:
            break
        ranked.extend(_round_robin_by_brand(tier, remaining))

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
    tags_text = " ".join((*product.shopify_tags, *product.tags)).lower()
    description = (product.description or "").lower()

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


def _semantic_score(product: Product, semantic_query: str) -> float:
    """Score canonical intent concepts against the enriched product profile.

    Structured filtering has already enforced audience/age/product constraints;
    this score only improves ordering and can never admit an invalid card.
    """
    if not semantic_query.strip():
        return 0.0
    profile = ensure_product_semantics(product).semantics
    if profile is None:
        return 0.0
    query_tokens = {
        token for token in re.findall(r"[a-z0-9]+", semantic_query.lower())
        if len(token) > 2 and token not in SEMANTIC_STOP_WORDS
    }
    if not query_tokens:
        return 0.0
    text = profile.search_text
    overlap = sum(_contains_word(token, text) for token in query_tokens) / len(query_tokens)
    family_bonus = 0.2 if (
        profile.product_family
        and _contains_word(profile.product_family, semantic_query.lower())
    ) else 0.0
    occasion_bonus = 0.15 if any(
        _contains_word(occasion, semantic_query.lower())
        for occasion in profile.occasions
    ) else 0.0
    attribute_bonus = 0.15 if any(
        _contains_word(attribute, semantic_query.lower())
        for attribute in profile.attributes
        if len(attribute) > 2
    ) else 0.0
    return min(1.0, 0.6 * overlap + family_bonus + occasion_bonus + attribute_bonus)


def _occasion_evidence_score(product: Product) -> float:
    """Verified dressiness evidence used only to rank already-valid cards."""
    profile = ensure_product_semantics(product).semantics
    if profile is None:
        return 0.0
    embellishment_bonus = {
        "heavy": 0.45,
        "light": 0.18,
        "none": 0.0,
    }[profile.embellishment]
    formal_fabric_bonus = 0.2 if any(
        fabric in FORMAL_FABRICS for fabric in profile.fabrics
    ) else 0.0
    festive_bonus = min(0.2, 0.05 * len(profile.festive_markers))
    return min(1.0, profile.formality * 0.1 + embellishment_bonus + formal_fabric_bonus + festive_bonus)


def _matches_style_exclusions(product: Product, excluded_styles: list[str]) -> bool:
    if not excluded_styles:
        return True
    profile = ensure_product_semantics(product).semantics
    if profile is None:
        return True
    evidence_text = " ".join((
        profile.search_text,
        " ".join(profile.fabrics),
        " ".join(profile.attributes),
        " ".join(profile.festive_markers),
    )).lower()
    for excluded in excluded_styles:
        key = excluded.lower().strip()
        if key == "embellished" and profile.embellishment != "none":
            return False
        if key == "heavy embellishment" and profile.embellishment == "heavy":
            return False
        if key and _contains_word(key, evidence_text):
            return False
    return True


def _has_keyword_evidence(product: Product, keyword: str) -> bool:
    """Whether one explicit shopper attribute occurs anywhere in the listing.

    Session searches use this to require every grounded attribute. Scoring can
    still rank title/category evidence above tags/description afterwards.
    """
    return any(
        _contains_word(keyword.lower(), text)
        for text in (
            product.name.lower(),
            (product.category or "").lower(),
            " ".join((*product.shopify_tags, *product.tags)).lower(),
            (product.description or "").lower(),
        )
    )


def _core_matches_category(core_text: str, requested_category: str) -> bool:
    """Match title/type while respecting specific sub-family contradictions."""
    canonical = re.sub(r"[^a-z0-9]+", " ", requested_category.lower()).strip()
    explicit_families = set(extract_garment_descriptors(core_text))
    if explicit_families & _CATEGORY_CHILDREN.get(canonical, set()):
        return True
    if not matches_garment_text(core_text, requested_category):
        return False
    if not explicit_families:
        return True
    return canonical in explicit_families


def _matches_requested_category(product: Product, requested_category: str) -> bool:
    """Require grounded garment-family evidence for every displayed card."""
    core_text = " ".join((product.name, product.category or ""))
    if _core_matches_category(core_text, requested_category):
        return True
    metadata_text = " ".join((*product.shopify_tags, *product.tags))
    # Merchant tags are only a fallback for genuinely generic titles/types.
    # A tag saying "Jackets" cannot turn an explicit vest into a jacket.
    return bool(
        matches_garment_text(metadata_text, requested_category)
        and set(extract_garment_descriptors(core_text)) == {"top"}
    )


def _query_keywords(query: str) -> list[str]:
    normalized_query = re.sub(r"\bdress(?:ed)?\s+up\b", " ", query.lower())
    raw = re.findall(r"[a-zA-Z0-9'-]+", normalized_query)
    expanded: list[str] = []
    for word in raw:
        key = word.strip("'-")
        if key in QUERY_ALIASES:
            expanded.extend(QUERY_ALIASES[key])
        elif key not in GENERIC_QUERY_WORDS:
            expanded.append(key)
    return list(dict.fromkeys(expanded))


def _dedupe_color_variants(products: list[Product], requested_color: str | None) -> list[Product]:
    """Collapse same-design cards that a merchant split by color."""
    if not requested_color:
        return products
    color = requested_color.lower()
    seen: set[tuple[str, str]] = set()
    result: list[Product] = []
    for product in products:
        title = re.sub(rf"\b{re.escape(color)}\b", " ", product.name.lower())
        title = re.sub(r"\b(default|colour|color|variant)\b", " ", title)
        normalized_title = re.sub(r"[^a-z0-9]+", " ", title).strip()
        key = (_brand_slug(product), normalized_title)
        if key not in seen:
            seen.add(key)
            result.append(product)
    return result


def _apply_filters(
    products: list[Product],
    occasion: str | None = None,
    color: str | None = None,
    size: str | None = None,
    tags: list[str] | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    kids: bool = False,
    child_age_months: int | None = None,
    department: str | None = None,
    audience_scoped: bool = False,
    min_formality: int | None = None,
    excluded_styles: list[str] | None = None,
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
        kids: If True, filter TO kids items only (shopping for a child).
            If False (default), filter kids items OUT — an adult's search
            shouldn't surface a toddler's outfit, but a shopper who says
            they're buying for a child should see only kids items, not a
            mix of both.

    Returns:
        Filtered products list
    """
    filtered = products if audience_scoped else _apply_audience_scope(
        products,
        kids=kids,
        child_age_months=child_age_months,
        department=department,
    )

    if occasion:
        filtered = [p for p in filtered if _cached_event_match_score(p, occasion) > 0]

    if color:
        color_matches = [
            (product, matching_color(color, product.colors))
            for product in filtered
        ]
        filtered = []
        for product, matched_color in color_matches:
            if matched_color is None:
                continue
            image = product.color_images.get(matched_color.lower())
            filtered.append(product.model_copy(update={"image": image}) if image else product)

    if size:
        requested_size = _normalized_size(size)
        filtered = [
            p for p in filtered
            if requested_size in {_normalized_size(available) for available in p.sizes}
        ]

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

    if min_formality is not None:
        filtered = [
            product for product in filtered
            if (
                ensure_product_semantics(product).semantics is not None
                and ensure_product_semantics(product).semantics.formality >= min_formality
            )
        ]

    if excluded_styles:
        filtered = [
            product for product in filtered
            if _matches_style_exclusions(product, excluded_styles)
        ]

    return filtered


def _apply_audience_scope(
    products: list[Product],
    *,
    kids: bool,
    child_age_months: int | None,
    department: str | None,
) -> list[Product]:
    """Apply cheap constraints that can safely precede category semantics.

    These exact gates are also reapplied before pagination. Running them first
    avoids parsing garment families across an entire adult catalog for a query
    that can only accept a few hundred age-compatible kids products.
    """
    filtered = [
        p for p in products
        if p.is_kids == kids
        and not is_non_apparel_listing(
            p.name,
            p.category,
            p.shopify_tags,
        )
    ]

    if department:
        # Audience is a hard constraint. Treating unknown metadata as a match
        # caused women-modelled kurtis from mixed catalogs to appear in a
        # result set explicitly described as men's. Unknown is not evidence
        # that a product belongs to the requested department.
        filtered = [
            p for p in filtered
            if p.department in {department, "unisex"}
        ]

    if child_age_months is not None:
        # Age is a hard safety/relevance constraint. Products with unknown
        # age metadata are excluded rather than guessed, and this filter is
        # never relaxed by SessionService when the result set is small.
        filtered = [
            p for p in filtered
            if p.is_kids and product_supports_age(p, child_age_months)
        ]

    return filtered


class SearchService:
    """Product search with keyword scoring and filtering."""

    @staticmethod
    def search(
        products: list[Product],
        query: str = "",
        category: str | None = None,
        occasion: str | None = None,
        color: str | None = None,
        size: str | None = None,
        tags: list[str] | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        page: int = 1,
        page_size: int = 20,
        kids: bool = False,
        child_age_months: int | None = None,
        department: str | None = None,
        require_all_keywords: bool = False,
        semantic_query: str | None = None,
        min_formality: int | None = None,
        excluded_styles: list[str] | None = None,
        occasion_as_signal: bool = False,
        strict_classification: bool = True,
    ) -> ProductSearchResponse:
        """Search products with keyword scoring and filters.

        Args:
            products: Candidate products (from cache)
            query: Free-text search query
            category: Hard product family selected from the conversation
            occasion: Filter by occasion
            color: Filter by color
            size: Filter by size
            tags: Filter by tags (all must match)
            max_price: Maximum price
            min_price: Minimum price
            page: Page number (1-indexed)
            page_size: Results per page
            kids: If True, search kids items only; if False (default),
                exclude them from an ordinary adult search.

        Returns:
            Paginated ProductSearchResponse with scored results
        """
        # Parse keywords from query
        keywords = _query_keywords(query)
        requested_category = category or extract_primary_garment(query)

        # Apply cheap, strict evidence before expensive occasion suitability.
        # A common vibe query can reduce a multi-thousand-product catalog to a
        # few dozen candidates; evaluating cultural event rules on the full
        # catalog first made otherwise warm searches take tens of seconds.
        candidates = _apply_audience_scope(
            products,
            kids=kids,
            child_age_months=child_age_months,
            department=department,
        )
        if requested_category:
            candidates = [
                product for product in candidates
                if _matches_requested_category(product, requested_category)
            ]
        if require_all_keywords and keywords:
            candidates = [
                product for product in candidates
                if all(_has_keyword_evidence(product, keyword) for keyword in keywords)
            ]

        # Apply filters
        strict_occasion = None if occasion_as_signal else occasion
        filtered = _apply_filters(
            candidates,
            occasion=strict_occasion,
            color=color,
            size=size,
            tags=tags,
            max_price=max_price,
            min_price=min_price,
            kids=kids,
            child_age_months=child_age_months,
            department=department,
            audience_scoped=True,
            min_formality=min_formality,
            excluded_styles=excluded_styles,
        )
        if strict_classification:
            filtered = [product for product in filtered if matches_classification(product, query)]

        # Score by keyword matches
        scored = []
        use_semantic_scoring = bool(
            semantic_query and len(filtered) <= SEMANTIC_SCORING_MAX_CANDIDATES
        )
        for product in filtered:
            keyword_score = _keyword_score(product, keywords)
            occasion_score = _cached_event_match_score(product, occasion) if occasion else 0.0
            semantic_score = (
                _semantic_score(product, semantic_query or "")
                if use_semantic_scoring
                else 0.0
            )
            occasion_evidence = _occasion_evidence_score(product) if occasion else 0.0
            # Coarse score tiers retain brand diversification while still
            # letting semantic relevance move better candidates upward.
            hybrid_score = round(
                (keyword_score + occasion_score + 0.75 * semantic_score + occasion_evidence) * 10
            ) / 10
            scored.append((product, hybrid_score))

        # Diversify across brands rather than a flat score/name sort (see
        # _diversify_by_brand — a flat sort clusters results by whichever
        # brand's product-naming convention wins ties alphabetically).
        # Normal chat requests only need one page. Keep an exact count for the
        # badge, but do not construct thousands of ranked Product objects that
        # will immediately be sliced away. Color searches still rank the full
        # set because variant de-duplication can change their exact total.
        relevant_total = sum(score > 0 for _, score in scored)
        end_idx = page * page_size
        ranking_limit = None if color else end_idx
        ranked_products = _dedupe_color_variants(
            _diversify_by_brand(scored, ranking_limit), requested_color=color
        )

        # Final response contract: revalidate every ranked card immediately
        # before pagination. This is intentionally defensive—future ranking,
        # diversification, or fallback changes must never reintroduce a card
        # that violates audience, adult/kids, exact age, apparel, occasion,
        # color, size, tags, or budget constraints.
        ranked_products = _apply_filters(
            ranked_products,
            occasion=strict_occasion,
            color=color,
            size=size,
            tags=tags,
            max_price=max_price,
            min_price=min_price,
            kids=kids,
            child_age_months=child_age_months,
            department=department,
            min_formality=min_formality,
            excluded_styles=excluded_styles,
        )
        if requested_category:
            ranked_products = [
                product for product in ranked_products
                if _matches_requested_category(product, requested_category)
            ]
        ranked_products = [
            product for product in ranked_products
            if (not strict_classification or matches_classification(product, query))
            and (
                not require_all_keywords
                or all(_has_keyword_evidence(product, keyword) for keyword in keywords)
            )
        ]

        # Paginate
        total = len(ranked_products) if color else relevant_total
        start_idx = (page - 1) * page_size
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
        kids: bool = False,
        child_age_months: int | None = None,
    ) -> ProductSearchResponse:
        """Filter products by brand slugs.

        Args:
            products: Candidate products
            brand_slugs: List of brand slugs to include
            page: Page number
            page_size: Results per page
            kids: If True, kids items only; if False (default), excluded —
                same reasoning as SearchService.search.

        Returns:
            Paginated results filtered by brand
        """
        filtered = [
            p for p in products
            if p.is_kids == kids
            and (child_age_months is None or product_supports_age(p, child_age_months))
            and any(p.id.startswith(f"{slug}:") for slug in brand_slugs)
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
