"""One-shot, current-store product search for the browser extension."""

import html
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urlsplit

from app.errors import ExternalServiceError
from app.schemas.extension import (
    CatalogRanking,
    ExtensionIntent,
    ExtensionProductResult,
    ExtensionSearchMeta,
    ExtensionSearchResponse,
)
from app.services.extension_catalog_service import ExtensionCatalogService
from app.nlp.pakistani_events import event_match_score
from app.schemas.product import Product
from app.shopify.mapper import map_shopify_to_product
from app.nlp.colors import colors_match, extract_color

logger = logging.getLogger(__name__)


class ExtensionIntentProvider(Protocol):
    async def parse_intent(
        self, query: str, previous_intent: ExtensionIntent | None = None
    ) -> ExtensionIntent: ...

    async def rank_candidates(
        self, descriptive: str, candidates: list[dict]
    ) -> list[CatalogRanking]: ...


class ExtensionSearchError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class VariantFact:
    price: float
    options: dict[str, str]
    image_url: str | None = None


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    product_type: str
    tags: list[str]
    image_url: str
    product_url: str
    variants: list[VariantFact]
    color_is_variant_option: bool
    size_is_variant_option: bool
    department: str | None
    is_kids: bool
    age_ranges_months: list[tuple[int, int]]

    @property
    def searchable_text(self) -> str:
        return " ".join((self.title, self.product_type, *self.tags)).lower()


SIZE_ALIASES = {
    "EXTRASMALL": "XS",
    "XSMALL": "XS",
    "SMALL": "S",
    "MEDIUM": "M",
    "LARGE": "L",
    "EXTRALARGE": "XL",
    "XLARGE": "XL",
    "XXLARGE": "XXL",
    "2XL": "XXL",
    "XXXLARGE": "XXXL",
    "3XL": "XXXL",
}

RANKING_PROMPT_CANDIDATE_LIMIT = 24

CATEGORY_ALIASES = {
    "shoes": ("shoe", "footwear", "sneaker", "sandal", "slide", "loafer", "heel", "flat"),
    "pants": ("pant", "trouser"),
    "polo": ("polo",),
    "tank top": ("tank top", "camisole"),
    "t-shirt": ("t shirt", "tee"),
}


def _plain_text(value: object, max_length: int = 120) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:max_length]


def _normalize_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_size(value: str) -> str:
    compact = re.sub(r"[^A-Z0-9]+", "", value.upper())
    return SIZE_ALIASES.get(compact, compact)


def _tags(raw: object) -> list[str]:
    if isinstance(raw, str):
        values = raw.split(",")
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    return [_plain_text(value, 60) for value in values if _plain_text(value, 60)][:60]


def _variant_options(product: dict, variant: dict) -> tuple[dict[str, str], bool, bool]:
    options: dict[str, str] = {}
    has_color = False
    has_size = False
    for index, option in enumerate(product.get("options") or [], start=1):
        if not isinstance(option, dict):
            continue
        name = _plain_text(option.get("name"), 40).lower()
        value = _plain_text(variant.get(f"option{index}"), 60)
        if not name or not value:
            continue
        options[name] = value
        has_color = has_color or "color" in name or "colour" in name
        has_size = has_size or "size" in name
    return options, has_color, has_size


def _candidate_from_shopify(product: dict, domain: str) -> Candidate | None:
    # Reuse the mature web catalog's apparel, stock, price, kids, and image
    # quality gates while retaining raw variants for exact conjunctions.
    mapped = map_shopify_to_product(
        product,
        "extension",
        domain,
        allow_footwear=True,
    )
    if mapped is None:
        return None

    variants: list[VariantFact] = []
    has_color_option = False
    has_size_option = False
    for variant in product.get("variants") or []:
        if not isinstance(variant, dict) or not variant.get("available", True):
            continue
        try:
            price = float(variant.get("price"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(price) or price < 0:
            continue
        options, variant_has_color, variant_has_size = _variant_options(product, variant)
        has_color_option = has_color_option or variant_has_color
        has_size_option = has_size_option or variant_has_size
        variant_color = next(
            (value for name, value in options.items() if "color" in name or "colour" in name),
            None,
        )
        variant_image = mapped.color_images.get(variant_color.lower()) if variant_color else None
        variants.append(VariantFact(price=price, options=options, image_url=variant_image))
    if not variants:
        return None

    product_id = str(product.get("id", ""))
    handle = _plain_text(product.get("handle"), 160)
    if not product_id or not handle:
        return None
    safe_handle = quote(handle, safe="-_")
    return Candidate(
        id=product_id,
        title=_plain_text(product.get("title"), 160),
        product_type=_plain_text(product.get("product_type"), 80),
        tags=_tags(product.get("tags")),
        image_url=mapped.image,
        product_url=f"https://{domain}/products/{safe_handle}",
        variants=variants,
        color_is_variant_option=has_color_option,
        size_is_variant_option=has_size_option,
        department=mapped.department,
        is_kids=mapped.is_kids,
        age_ranges_months=mapped.age_ranges_months,
    )


def _option_value(variant: VariantFact, kind: str) -> str | None:
    for name, value in variant.options.items():
        if kind == "color" and ("color" in name or "colour" in name):
            return value
        if kind == "size" and "size" in name:
            return value
    return None


def _matches_category(candidate: Candidate, category: str | None) -> bool:
    if not category:
        return True
    haystack = _normalize_words(candidate.searchable_text)
    canonical = _normalize_words(category)
    if canonical == "sleeve":
        # Outfitters encodes this inside compact tags such as
        # "M-TS-RegHalfSleeveXXL", not as a standalone product type.
        return "sleeve" in haystack.replace(" ", "") and "sleeveless" not in haystack
    aliases = CATEGORY_ALIASES.get(canonical)
    if aliases:
        return any(
            re.search(rf"\b{re.escape(_normalize_words(alias))}s?\b", haystack)
            for alias in aliases
        )
    terms = canonical.split()
    return bool(terms) and all(re.search(rf"\b{re.escape(term)}s?\b", haystack) for term in terms)


def _supports_child_age(candidate: Candidate, child_age_months: int | None) -> bool:
    if child_age_months is None:
        return True
    return any(start <= child_age_months <= end for start, end in candidate.age_ranges_months)


def _matching_variants(candidate: Candidate, intent: ExtensionIntent) -> list[VariantFact]:
    requested_size = _normalize_size(intent.size or "")
    product_text = _normalize_words(candidate.searchable_text)
    matches = []
    for variant in candidate.variants:
        if intent.price_min is not None and variant.price < intent.price_min:
            continue
        if intent.price_max is not None and variant.price > intent.price_max:
            continue

        if intent.color:
            color_value = _option_value(variant, "color")
            if candidate.color_is_variant_option:
                if not color_value or not colors_match(intent.color, color_value):
                    continue
            elif not (
                (text_color := extract_color(product_text))
                and colors_match(intent.color, text_color)
            ):
                continue

        if intent.size:
            size_value = _option_value(variant, "size")
            if candidate.size_is_variant_option:
                if not size_value or _normalize_size(size_value) != requested_size:
                    continue
            elif requested_size not in {"ONESIZE", "OS"}:
                continue
        matches.append(variant)
    return matches


def _structured_reason(intent: ExtensionIntent) -> str:
    facts: list[str] = []
    if intent.color:
        facts.append(f"{intent.color.title()} option")
    if intent.size:
        facts.append(f"size {intent.size.upper()}")
    if intent.price_max is not None:
        facts.append("within your budget")
    if intent.price_min is not None and intent.price_max is None:
        facts.append("above your minimum price")
    if intent.category:
        facts.append(f"matches {intent.category}")
    if intent.occasion:
        facts.append(f"suited to {intent.occasion}")
    if intent.audience:
        facts.append(f"from the {intent.audience}'s department")
    if intent.wants_kids:
        facts.append("from the kids' range")
    if not facts:
        return "Matches the details in your request."
    if len(facts) == 1:
        return facts[0][0].upper() + facts[0][1:] + "."
    prefix = ", ".join(facts[:-1])
    return prefix[0].upper() + prefix[1:] + f", and {facts[-1]}."


def _result_image(candidate: Candidate, variants: list[VariantFact]) -> str:
    return next((variant.image_url for variant in variants if variant.image_url), candidate.image_url)


def _metadata_score(candidate: Candidate, intent: ExtensionIntent) -> float:
    score = 0.0
    if intent.category and _matches_category(candidate, intent.category):
        score += 5.0
    if intent.occasion:
        score += _candidate_event_score(candidate, intent.occasion) * 5.0
    for term in _normalize_words(intent.descriptive or "").split():
        if len(term) > 2 and re.search(rf"\b{re.escape(term)}s?\b", candidate.searchable_text):
            score += 1.0
    return score


def _candidate_event_score(candidate: Candidate, occasion: str) -> float:
    colors = sorted({
        value
        for variant in candidate.variants
        if (value := _option_value(variant, "color"))
    })
    product = Product(
        id=f"extension:{candidate.id}",
        name=candidate.title,
        category=candidate.product_type or None,
        description="",
        price=min(variant.price for variant in candidate.variants),
        colors=colors,
        tags=candidate.tags,
        shopify_tags=candidate.tags,
        image=candidate.image_url,
        product_url=candidate.product_url,
    )
    return event_match_score(product, occasion)


class ExtensionSearchService:
    def __init__(
        self,
        catalog_service: ExtensionCatalogService,
        intent_provider: ExtensionIntentProvider,
        allowed_domains: set[str],
        rank_candidate_limit: int = 40,
        result_limit: int = 40,
    ):
        self._catalog_service = catalog_service
        self._provider = intent_provider
        self._allowed_domains = {domain.lower().rstrip(".") for domain in allowed_domains}
        self._rank_candidate_limit = min(max(rank_candidate_limit, 1), 100)
        self._result_limit = min(max(result_limit, 1), 40)

    def validate_store_origin(self, store_origin: str) -> str:
        parsed = urlsplit(store_origin)
        domain = (parsed.hostname or "").lower().rstrip(".")
        if (
            parsed.scheme != "https"
            or not domain
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or domain not in self._allowed_domains
        ):
            raise ExtensionSearchError(
                "UNSUPPORTED_STORE",
                "Open Outfitters in the active tab to use this MVP.",
                400,
            )
        # Prefer the registered apex host so cache keys and product URLs stay stable.
        apex = domain.removeprefix("www.")
        return apex if apex in self._allowed_domains else domain

    async def search(
        self,
        query: str,
        store_origin: str,
        previous_intent: ExtensionIntent | None = None,
    ) -> ExtensionSearchResponse:
        started = time.monotonic()
        domain = self.validate_store_origin(store_origin)
        intent = await self._provider.parse_intent(query.strip(), previous_intent)
        if not intent.has_any_signal():
            raise ExtensionSearchError(
                "EMPTY_INTENT",
                "Add a product, style, occasion, color, size, or budget so Dhaaga knows what to find.",
                422,
            )

        catalog = await self._catalog_service.get_catalog(domain)
        candidates = [
            candidate
            for raw in catalog.products
            if isinstance(raw, dict)
            if (candidate := _candidate_from_shopify(raw, domain)) is not None
        ]

        strict: list[tuple[Candidate, list[VariantFact]]] = []
        for candidate in candidates:
            if candidate.is_kids != (intent.wants_kids is True):
                continue
            if not _supports_child_age(candidate, intent.child_age_months):
                continue
            if intent.audience and candidate.department not in {intent.audience, "unisex"}:
                continue
            if not _matches_category(candidate, intent.category):
                continue
            if intent.occasion and _candidate_event_score(candidate, intent.occasion) <= 0:
                continue
            matching = _matching_variants(candidate, intent)
            if matching:
                strict.append((candidate, matching))

        relaxed = False
        relaxed_filters: list[str] = []
        selected = strict

        selected.sort(key=lambda item: (-_metadata_score(item[0], intent), min(v.price for v in item[1])))
        selected = selected[: self._rank_candidate_limit]

        results: list[ExtensionProductResult]
        ranking_description = " ".join(
            value for value in (intent.descriptive, intent.occasion) if value
        )
        if ranking_description and selected:
            ranking_selected = selected[:RANKING_PROMPT_CANDIDATE_LIMIT]
            ranking_input = [
                {
                    "id": candidate.id,
                    "title": candidate.title[:90],
                    "product_type": candidate.product_type[:45],
                    "tags": [tag[:36] for tag in candidate.tags[:6]],
                }
                for candidate, _ in ranking_selected
            ]
            try:
                rankings = await self._provider.rank_candidates(ranking_description, ranking_input)
            except ExternalServiceError as error:
                # A ranking outage should not erase already-valid structured
                # matches. Keep the deterministic order and explain it with
                # facts we verified locally instead of returning a generic 502.
                logger.warning("Extension descriptive ranking unavailable; using metadata order: %s", error)
                rankings = []
            by_id = {ranking.id: ranking for ranking in rankings}
            if by_id:
                ranked_selected = [item for item in ranking_selected if item[0].id in by_id]
                ranked_selected.sort(key=lambda item: by_id[item[0].id].score, reverse=True)
                ranked_results = [
                    ExtensionProductResult(
                        id=candidate.id,
                        title=candidate.title,
                        price=min(variant.price for variant in matching_variants),
                        imageUrl=_result_image(candidate, matching_variants),
                        productUrl=candidate.product_url,
                        score=by_id[candidate.id].score,
                        reason=by_id[candidate.id].reason,
                    )
                    for candidate, matching_variants in ranked_selected
                ]
                ranked_ids = {candidate.id for candidate, _ in ranked_selected}
                fallback_results = [
                    ExtensionProductResult(
                        id=candidate.id,
                        title=candidate.title,
                        price=min(variant.price for variant in matching_variants),
                        imageUrl=_result_image(candidate, matching_variants),
                        productUrl=candidate.product_url,
                        score=min(10, max(1, _metadata_score(candidate, intent))),
                        reason=_structured_reason(intent),
                    )
                    for candidate, matching_variants in selected
                    if candidate.id not in ranked_ids
                ]
                results = (ranked_results + fallback_results)[: self._result_limit]
            else:
                results = [
                    ExtensionProductResult(
                        id=candidate.id,
                        title=candidate.title,
                        price=min(variant.price for variant in matching_variants),
                        imageUrl=_result_image(candidate, matching_variants),
                        productUrl=candidate.product_url,
                        score=min(10, max(1, _metadata_score(candidate, intent))),
                        reason=_structured_reason(intent),
                    )
                    for candidate, matching_variants in selected[: self._result_limit]
                ]
        else:
            results = [
                ExtensionProductResult(
                    id=candidate.id,
                    title=candidate.title,
                    price=min(variant.price for variant in matching_variants),
                    imageUrl=_result_image(candidate, matching_variants),
                    productUrl=candidate.product_url,
                    score=10,
                    reason=_structured_reason(intent),
                )
                for candidate, matching_variants in selected[: self._result_limit]
            ]

        notice = None
        if relaxed:
            notice = "No exact matches for every filter. Showing the closest picks instead."
        if catalog.capped:
            partial = f"Searched the first {len(catalog.products)} products; results may be partial."
            notice = f"{notice} {partial}" if notice else partial

        return ExtensionSearchResponse(
            intent=intent,
            products=results,
            notice=notice,
            meta=ExtensionSearchMeta(
                storeDomain=domain,
                fetchedCount=len(catalog.products),
                catalogCapped=catalog.capped,
                relaxed=relaxed,
                relaxedFilters=relaxed_filters,
                durationMs=int((time.monotonic() - started) * 1000),
            ),
        )
