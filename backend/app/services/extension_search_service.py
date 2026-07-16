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
    ExtensionMatchDetails,
    ExtensionProductResult,
    ExtensionSearchMeta,
    ExtensionSearchResponse,
)
from app.services.extension_catalog_service import ExtensionCatalogService
from app.nlp.pakistani_events import event_match_score
from app.schemas.product import Product
from app.shopify.mapper import map_shopify_to_product
from app.nlp.colors import colors_match, extract_color
from app.nlp.apparel_classification import extract_classification_request, matches_classification

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
    "activewear": (
        "activewear", "sportswear", "athleisure", "performance", "training",
        "dri fit", "moisture wicking", "compression", "sports hijab",
        "sports abaya", "sports bra", "bike short", "yoga pant", "track pant",
        "jogger", "windbreaker", "running shoe", "trainer",
    ),
    "swimwear": ("swimwear", "swimsuit", "bathing suit"),
    "shoes": (
        "shoe", "footwear", "sneaker", "sandal", "slide", "loafer", "heel",
        "flat", "khussa", "trainer", "boot", "dress shoe", "oxford", "derby", "pump",
    ),
    "pants": ("pant", "trouser"),
    "polo": ("polo",),
    "tank top": ("tank top", "camisole"),
    "t-shirt": ("t shirt", "tee"),
    "sweater": ("sweater", "knitwear", "pullover", "jumper"),
    "jacket": ("jacket", "outerwear", "bomber", "puffer", "windbreaker"),
    "belt": ("belt",),
    "shalwar kameez": ("shalwar kameez", "salwar kameez", "eastern suit"),
    "shirt dress": ("shirt dress",),
    "wrap dress": ("wrap dress",),
    "cocktail dress": ("cocktail dress",),
    "slip dress": ("slip dress",),
    "maxi": ("maxi", "maxi dress"),
    "gown": ("gown", "long dress"),
    "blouse": ("blouse",),
    "crop top": ("crop top",),
    "peplum top": ("peplum", "peplum top"),
    "tunic": ("tunic",),
    "kurti": ("kurti", "short kurta"),
    "kameez": ("kameez",),
    "suit": ("suit", "2 piece", "3 piece", "two piece", "three piece"),
    "palazzo": ("palazzo",),
    "cigarette pants": ("cigarette pant", "cigarette trouser"),
    "shalwar": ("shalwar", "salwar"),
    "gharara": ("gharara",),
    "sharara": ("sharara",),
    "leggings": ("legging", "tights"),
    "blazer": ("blazer", "suit jacket"),
    "waistcoat": ("waistcoat", "waist coat"),
    "shrug": ("shrug",),
    "cape": ("cape",),
    "cardigan": ("cardigan",),
    "sherwani": ("sherwani",),
    "achkan": ("achkan",),
    "windbreaker": ("windbreaker", "training jacket"),
    "sports bra": ("sports bra",),
    "joggers": ("jogger", "track pant"),
    "jumpsuit": ("jumpsuit",),
}

FIT_ALIASES = {
    "wide leg": ("wide leg", "wideleg"),
    "boot cut": ("boot cut", "bootcut"),
    "straight": ("straight",),
    "skinny": ("skinny",),
    "slim": ("slim",),
    "baggy": ("baggy",),
    "relaxed": ("relaxed",),
    "flared": ("flared", "flare"),
    "cropped": ("cropped",),
    "oversized": ("oversized", "over sized"),
    "loose": ("loose",),
    "regular": ("regular fit",),
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


def _matches_fit(candidate: Candidate, fit: str | None) -> bool:
    if not fit:
        return True
    haystack = _normalize_words(candidate.searchable_text)
    aliases = FIT_ALIASES.get(_normalize_words(fit), (_normalize_words(fit),))
    return any(
        re.search(rf"\b{re.escape(_normalize_words(alias))}\b", haystack)
        for alias in aliases
    )


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
            requested_colors = [
                color.strip()
                for color in re.split(r"\s+or\s+", intent.color, flags=re.IGNORECASE)
                if color.strip()
            ]
            color_value = _option_value(variant, "color")
            if candidate.color_is_variant_option:
                if not color_value or not any(
                    colors_match(requested, color_value) for requested in requested_colors
                ):
                    continue
            elif not (
                (text_color := extract_color(product_text))
                and any(colors_match(requested, text_color) for requested in requested_colors)
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


def _requested_colors(intent: ExtensionIntent) -> list[str]:
    return [
        color.strip()
        for color in re.split(r"\s+or\s+", intent.color or "", flags=re.IGNORECASE)
        if color.strip()
    ]


def _variants_matching_color(
    candidate: Candidate,
    variants: list[VariantFact],
    intent: ExtensionIntent,
) -> list[VariantFact]:
    requested_colors = _requested_colors(intent)
    if not requested_colors:
        return variants
    if candidate.color_is_variant_option:
        return [
            variant
            for variant in variants
            if (color_value := _option_value(variant, "color"))
            and any(colors_match(requested, color_value) for requested in requested_colors)
        ]
    product_color = extract_color(_normalize_words(candidate.searchable_text))
    if product_color and any(colors_match(requested, product_color) for requested in requested_colors):
        return variants
    return []


def _preference_fields(intent: ExtensionIntent) -> tuple[str, ...]:
    fields: list[str] = []
    if intent.fit:
        fields.append("fit")
    if intent.color:
        fields.append("color")
    if intent.occasion:
        fields.append("occasion")
    classification = extract_classification_request(intent.descriptive or "")
    if classification.formality or classification.activewear:
        fields.append("formality")
    if classification.tradition:
        fields.append("family")
    return tuple(fields)


def _category_contradicts_requested_style(intent: ExtensionIntent) -> bool:
    request = extract_classification_request(intent.descriptive or "")
    category = _normalize_words(intent.category or "")
    inherently_casual = {"t shirt", "jeans", "shorts", "sneakers"}
    inherently_formal = {"sherwani", "gharara", "sharara", "bridal gown"}
    if request.formality in {"formal", "party", "bridal"} and category in inherently_casual:
        return True
    if request.formality == "casual" and category in inherently_formal:
        return True
    return False


def _requested_family(intent: ExtensionIntent) -> str | None:
    descriptive = (intent.descriptive or "").lower()
    return next(
        (value for value in ("eastern", "western") if value in descriptive),
        None,
    )


def _matched_preferences(
    candidate: Candidate,
    variants: list[VariantFact],
    intent: ExtensionIntent,
) -> set[str]:
    matched: set[str] = set()
    if intent.fit and _matches_fit(candidate, intent.fit):
        matched.add("fit")
    if intent.color and _variants_matching_color(candidate, variants, intent):
        matched.add("color")
    if intent.occasion and _candidate_event_score(candidate, intent.occasion) > 0:
        matched.add("occasion")
    classification = extract_classification_request(intent.descriptive or "")
    if classification.formality or classification.activewear:
        classification_match = matches_classification(
            candidate.searchable_text,
            intent.descriptive,
        )
        formal_footwear = bool(
            classification.formality == "formal"
            and _matches_category(candidate, "shoes")
            and re.search(
                r"\b(?:loafers?|pumps?|flats?|heels?|oxfords?|derbys?)\b",
                _normalize_words(candidate.searchable_text),
            )
        )
        if classification_match or formal_footwear:
            matched.add("formality")
    if classification.tradition and matches_classification(
        candidate.searchable_text, intent.descriptive
    ):
        matched.add("family")
    return matched


def _preference_score(
    candidate: Candidate,
    variants: list[VariantFact],
    intent: ExtensionIntent,
    query: str,
) -> float:
    matched = _matched_preferences(candidate, variants, intent)
    preference_wording = bool(
        re.search(r"\b(?:preferably|ideally|if possible|would be nice|crapper)\b", query, re.IGNORECASE)
    )
    score = 0.0
    if "fit" in matched:
        score += 4.0
    if "color" in matched:
        score += 1.5 if preference_wording and intent.fit else 3.0
    if "occasion" in matched:
        score += 2.5 + _candidate_event_score(candidate, intent.occasion or "") * 2.0
    if "formality" in matched:
        score += 3.5
        if extract_classification_request(intent.descriptive or "").formality == "formal":
            searchable = _normalize_words(candidate.searchable_text)
            if re.search(r"\b(?:loafers?|oxfords?|derbys?|dress shoes?)\b", searchable):
                score += 2.0
            elif re.search(r"\b(?:pumps?|heels?)\b", searchable):
                score += 1.5
            elif re.search(r"\bflats?\b", searchable):
                score += 1.0
    if "family" in matched:
        score += 3.5
    return score


def _candidate_reason(
    candidate: Candidate,
    variants: list[VariantFact],
    intent: ExtensionIntent,
) -> str:
    matched = _matched_preferences(candidate, variants, intent)
    truthful_intent = intent.model_copy(update={
        "color": intent.color if "color" in matched else None,
        "fit": intent.fit if "fit" in matched else None,
        "occasion": intent.occasion if "occasion" in matched else None,
    })
    reason = _structured_reason(truthful_intent)
    if "formality" in matched:
        request = extract_classification_request(intent.descriptive or "")
        label = "activewear" if request.activewear else request.formality
        if label:
            return f"{label.title()} styling; {reason[0].lower()}{reason[1:]}"
    return reason


def _freeform_ranking_description(intent: ExtensionIntent) -> str:
    """Keep AI ranking for subjective language, not verified structure.

    Deterministic code already handles fit, event, formality, tradition, color,
    size, and price. Letting the model re-rank those fields caused factual
    inversions such as formal loafers being placed below casual slides.
    """
    text = intent.descriptive or ""
    structural_phrases = [
        intent.fit,
        intent.occasion,
        "semi-formal", "semi formal", "formal", "casual", "party", "bridal",
        "activewear", "sportswear", "eastern", "western", "fusion",
    ]
    for phrase in structural_phrases:
        if phrase:
            text = re.sub(rf"\b{re.escape(phrase)}\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _structured_reason(intent: ExtensionIntent) -> str:
    facts: list[str] = []
    if intent.color:
        facts.append(f"{intent.color.title().replace(' Or ', ' or ')} option")
    if intent.size:
        facts.append(f"size {intent.size.upper()}")
    if intent.fit:
        facts.append(f"{intent.fit} fit")
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
    if len(facts) == 2:
        sentence = f"{facts[0]} and {facts[1]}"
        return sentence[0].upper() + sentence[1:] + "."
    prefix = ", ".join(facts[:-1])
    return prefix[0].upper() + prefix[1:] + f", and {facts[-1]}."


def _result_image(
    candidate: Candidate,
    variants: list[VariantFact],
    intent: ExtensionIntent,
) -> tuple[str, bool | None]:
    variant_image = next((variant.image_url for variant in variants if variant.image_url), None)
    if intent.color:
        # A requested color can be verified as available while Shopify still
        # provides only a generic/primary product image. Preserve the valid
        # product but tell the client when the preview is not color-verified.
        return variant_image or candidate.image_url, variant_image is not None
    return variant_image or candidate.image_url, None


def _build_product_result(
    candidate: Candidate,
    matching_variants: list[VariantFact],
    intent: ExtensionIntent,
    *,
    score: float,
    reason: str,
) -> ExtensionProductResult:
    image_url, image_matches_color = _result_image(candidate, matching_variants, intent)
    colors = sorted({
        value
        for variant in matching_variants
        if (value := _option_value(variant, "color"))
    })
    sizes = sorted({
        value
        for variant in matching_variants
        if (value := _option_value(variant, "size"))
    })
    return ExtensionProductResult(
        id=candidate.id,
        title=candidate.title,
        price=min(variant.price for variant in matching_variants),
        imageUrl=image_url,
        productUrl=candidate.product_url,
        score=score,
        reason=reason,
        matchDetails=ExtensionMatchDetails(
            colors=colors if intent.color else [],
            sizes=sizes if intent.size else [],
            fit=intent.fit if intent.fit else None,
            occasion=intent.occasion if intent.occasion else None,
            audience=candidate.department if intent.audience else None,
            imageMatchesColor=image_matches_color,
        ),
    )


def _metadata_score(candidate: Candidate, intent: ExtensionIntent) -> float:
    score = 0.0
    if intent.category and _matches_category(candidate, intent.category):
        score += 5.0
    if intent.fit and _matches_fit(candidate, intent.fit):
        score += 3.0
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

        # Stable identity and variant facts remain exact. Occasion and fit are
        # recommendation signals: exact products lead, then closely related
        # products fill the remaining result slots without making false claims.
        classification_request = extract_classification_request(intent.descriptive or "")

        def collect_hard_matches(
            search_intent: ExtensionIntent,
            *,
            require_occasion: bool = True,
            require_fit: bool = True,
        ):
            matches: list[tuple[Candidate, list[VariantFact]]] = []
            for candidate in candidates:
                if candidate.is_kids != (search_intent.wants_kids is True):
                    continue
                if not _supports_child_age(candidate, search_intent.child_age_months):
                    continue
                if search_intent.audience and candidate.department not in {search_intent.audience, "unisex"}:
                    continue
                if not _matches_category(candidate, search_intent.category):
                    continue
                if require_fit and search_intent.fit and not _matches_fit(candidate, search_intent.fit):
                    continue
                if (
                    require_occasion
                    and
                    search_intent.occasion
                    and _candidate_event_score(candidate, search_intent.occasion) <= 0
                ):
                    continue
                if (
                    (
                        classification_request.formality
                        or classification_request.tradition
                        or classification_request.activewear
                    )
                    and not matches_classification(
                        candidate.searchable_text,
                        search_intent.descriptive,
                    )
                ):
                    continue
                matching = _matching_variants(candidate, search_intent)
                if matching:
                    matches.append((candidate, matching))
            return matches

        hard_matches = collect_hard_matches(intent)
        if _category_contradicts_requested_style(intent):
            hard_matches = []
        exact_count = len(hard_matches)
        selected = list(hard_matches)
        selected_ids = {candidate.id for candidate, _ in selected}
        match_tier = {candidate.id: 0 for candidate, _ in selected}
        effective_intents = {candidate.id: intent for candidate, _ in selected}
        relaxed = False
        relaxed_filters: list[str] = []

        def add_near_matches(
            matches: list[tuple[Candidate, list[VariantFact]]],
            tier: int,
        ) -> int:
            added = 0
            for candidate, variants in matches:
                if candidate.id in selected_ids:
                    continue
                updates = {}
                if (
                    intent.occasion
                    and _candidate_event_score(candidate, intent.occasion) <= 0
                ):
                    updates["occasion"] = None
                if intent.fit and not _matches_fit(candidate, intent.fit):
                    updates["fit"] = None
                selected.append((candidate, variants))
                selected_ids.add(candidate.id)
                match_tier[candidate.id] = tier
                effective_intents[candidate.id] = intent.model_copy(update=updates)
                added += 1
                if len(selected) >= self._result_limit:
                    break
            return added

        if len(selected) < self._result_limit and intent.occasion:
            added = add_near_matches(
                collect_hard_matches(intent, require_occasion=False),
                tier=1,
            )
            if added:
                relaxed = True
                relaxed_filters.append("occasion")

        if len(selected) < self._result_limit and intent.fit:
            added = add_near_matches(
                collect_hard_matches(
                    intent,
                    require_occasion=False,
                    require_fit=False,
                ),
                tier=2,
            )
            if added:
                relaxed = True
                relaxed_filters.append("fit")

        logger.info(
            "Extension eligibility: domain=%s fetched=%d mapped=%d exact=%d",
            domain,
            len(catalog.products),
            len(candidates),
            len(selected),
        )

        selected.sort(key=lambda item: (
            match_tier[item[0].id],
            -_preference_score(item[0], item[1], intent, query),
            -_metadata_score(item[0], intent),
            min(v.price for v in item[1]),
        ))
        selected = selected[: self._rank_candidate_limit]

        results: list[ExtensionProductResult]
        ranking_description = _freeform_ranking_description(intent)
        if ranking_description and selected:
            ranking_selected = selected[:RANKING_PROMPT_CANDIDATE_LIMIT]
            ranking_input = [
                {
                    "id": candidate.id,
                    "title": candidate.title[:90],
                    "product_type": candidate.product_type[:45],
                    "tags": [tag[:36] for tag in candidate.tags[:10]],
                    "colors": sorted({
                        color
                        for variant in matching_variants
                        if (color := _option_value(variant, "color"))
                    })[:8],
                }
                for candidate, matching_variants in ranking_selected
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
                ranked_selected.sort(key=lambda item: (
                    match_tier[item[0].id],
                    -_preference_score(item[0], item[1], intent, query),
                    -by_id[item[0].id].score,
                ))
                ranked_results = [
                    _build_product_result(
                        candidate,
                        matching_variants,
                        effective_intents[candidate.id],
                        score=by_id[candidate.id].score,
                        reason=by_id[candidate.id].reason,
                    )
                    for candidate, matching_variants in ranked_selected
                ]
                ranked_ids = {candidate.id for candidate, _ in ranked_selected}
                fallback_results = [
                    _build_product_result(
                        candidate,
                        matching_variants,
                        effective_intents[candidate.id],
                        score=min(10, max(1, _metadata_score(candidate, intent))),
                        reason=_candidate_reason(candidate, matching_variants, intent),
                    )
                    for candidate, matching_variants in selected
                    if candidate.id not in ranked_ids
                ]
                results = (ranked_results + fallback_results)[: self._result_limit]
            else:
                results = [
                    _build_product_result(
                        candidate,
                        matching_variants,
                        effective_intents[candidate.id],
                        score=min(10, max(1, _metadata_score(candidate, intent))),
                        reason=_candidate_reason(candidate, matching_variants, intent),
                    )
                    for candidate, matching_variants in selected[: self._result_limit]
                ]
        else:
            results = [
                _build_product_result(
                    candidate,
                    matching_variants,
                    effective_intents[candidate.id],
                    score=10,
                    reason=_candidate_reason(candidate, matching_variants, intent),
                )
                for candidate, matching_variants in selected[: self._result_limit]
            ]

        notice = (
            "Exact matches are shown first, followed by the closest relevant alternatives."
            if relaxed else None
        )
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
                mappedCount=len(candidates),
                exactCount=exact_count,
                catalogCapped=catalog.capped,
                relaxed=relaxed,
                relaxedFilters=relaxed_filters,
                durationMs=int((time.monotonic() - started) * 1000),
            ),
        )
