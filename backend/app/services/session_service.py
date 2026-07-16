"""Chat turn orchestration: fast-path -> query cache -> LLM -> merge -> search."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from time import perf_counter
from uuid import UUID, uuid4

from starlette.concurrency import run_in_threadpool

from app.errors import ExternalServiceError
from app.llm.fallback import FallbackIntentProvider
from app.nlp.diff_merge import merge_session_state
from app.kids_age import extract_age_ranges, extract_child_age_months
from app.nlp.fast_path_classifier import (
    classify,
    extract_budget_max,
    extract_department,
    extract_excluded_styles,
    extract_size,
    is_control_message,
    is_kids_request,
)
from app.nlp.apparel_classification import BRIDAL, FORMAL, PARTY, extract_classification_request
from app.nlp.garments import (
    extract_primary_garment,
    ground_style_descriptors,
    without_garment_descriptors,
)
from app.nlp.pakistani_events import event_garments, extract_event, is_known_event
from app.nlp.colors import extract_color
from app.repositories.brand_repo import BrandRepository
from app.repositories.chat_repo import ChatRepository
from app.repositories.events_repo import SessionEventRepository
from app.repositories.query_cache_repo import QueryCacheRepository
from app.schemas.product import Product, ProductSearchResponse
from app.schemas.session import ChatTurnResponse, IntentExtractionResult, SessionState
from app.services.product_cache_service import ProductCacheService
from app.services.live_product_service import LiveProductValidationService
from app.services.search_service import SearchService
from app.session_store.base import SessionStore

logger = logging.getLogger(__name__)

# Garment families that shoppers reasonably compare when an exact product is
# unavailable. These are deliberately narrow, culturally meaningful
# alternatives rather than a generic "show anything" fallback.
NEAR_MATCH_CATEGORIES: dict[str, tuple[str, ...]] = {
    "sherwani": ("prince coat", "achkan", "waistcoat", "kurta", "shalwar kameez"),
    "achkan": ("sherwani", "prince coat", "waistcoat", "kurta"),
    "prince coat": ("sherwani", "achkan", "waistcoat", "kurta"),
    "gharara": ("sharara", "lehenga", "formal suit", "maxi"),
    "sharara": ("gharara", "lehenga", "formal suit", "maxi"),
    "lehenga": ("gharara", "sharara", "formal suit", "maxi"),
}
timing_logger = logging.getLogger("uvicorn.error")

MIN_RESULTS_BEFORE_RELAX = 10  # retained for compatibility/telemetry
DEFAULT_PAGE_SIZE = 24
INTENT_CACHE_VERSION = "llm-intent-v4"

# How many of {occasion, budget, color/style/garment, size} must be known
# before showing products at all, rather than asking another follow-up.
# Once this many signals are known they persist across turns (merge_session_state
# accumulates/overwrites, never silently clears), so this only gates the
# *first* couple of turns on a vague query — it never re-hides results
# already being shown.
MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS = 2

# Older registries marked this single-audience catalog as unisex. Keep the
# runtime correction alongside migration 0003 so already-decoded cache entries
# are repaired too.
KNOWN_BRAND_DEPARTMENTS = {
    "generation": "women",
}

_CATEGORY_REFINEMENT_PATTERN = re.compile(
    r"\b(?:instead|switch|replace|change (?:it|them)?\s*to|same .+ but)\b",
    re.IGNORECASE,
)
_OCCASION_REFINEMENT_PATTERN = re.compile(
    r"(?:^|\b)(?:for|to)\s+(?:a\s+|the\s+|my\s+)?(?:mehndi|mayun|ubtan|"
    r"dholki|sangeet|nikah|nikkah|wedding|shaadi|baraat|walima|valima|eid|"
    r"office|party|dawat|qawwali|milad|iftar)\b|\b(?:instead|switch)\b",
    re.IGNORECASE,
)
_KIDS_TOPIC_PATTERN = re.compile(
    r"\b(?:kids?|children'?s?|juniors?)\s+(?:clothes|cloths|clothing|wear)\b",
    re.IGNORECASE,
)

GENDERED_GARMENT_TERMS = {
    "lehenga", "gharara", "sharara", "pishwas", "sari", "saree", "abaya",
    "frock", "gown", "maxi", "dress", "sherwani", "prince coat", "blazer",
    "waistcoat", "kurta", "shalwar kameez", "kameez",
}

VALID_FALLBACK_STYLES = {
    "formal", "semi-formal", "party", "festive", "embroidered",
    "printed", "traditional", "eastern", "silk", "chiffon", "organza",
    "velvet", "satin", "lawn", "simple", "understated",
}


def _styles_after_department_switch(styles: list[str]) -> list[str]:
    """Keep neutral aesthetics but discard old audience-specific garments."""
    return [
        style for style in styles
        if not any(term in style.lower() for term in GENDERED_GARMENT_TERMS)
    ]


def _known_signal_count(state: SessionState) -> int:
    return sum([
        bool(state.occasion),
        bool(state.category),
        state.budget_max is not None,
        bool(state.color_preference),
        bool(state.style_descriptors),
        bool(state.size),
        state.wants_kids,
    ])


def _no_results_reply(state: SessionState) -> str:
    """A good-mannered reply for a genuine miss — the shopper asked for
    something specific enough that nothing in the current catalog matches
    it, rather than the query just being too vague to narrow (that case
    never reaches a search at all, see MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS)."""
    if state.child_age_months is not None:
        age = (
            f"{state.child_age_months} months"
            if state.child_age_months < 24
            else f"{state.child_age_months // 12} years"
        )
        return (
            f"I'm sorry, we don't currently have an option explicitly sized for age {age} "
            "that matches the rest of your request. I won't substitute an older child's size."
        )
    audience = "men's" if state.department == "men" else "women's" if state.department == "women" else None
    details = [
        audience,
        state.color_preference,
        *state.style_descriptors,
        state.category,
        f"for {state.occasion}" if state.occasion else None,
    ]
    what = " ".join(dict.fromkeys(value for value in details if value)) or "that request"
    return (
        f"I couldn't find an exact match for {what}. I kept every confirmed detail "
        "strict—remove one filter below to broaden the results."
    )


def _results_reply(state: SessionState, total: int) -> str:
    details = [state.color_preference, *state.style_descriptors, state.category]
    description = " ".join(dict.fromkeys(item for item in details if item))
    if state.wants_kids:
        if state.child_age_months is None:
            audience = "kids'"
        elif state.child_age_months < 24:
            audience = f"kids' for age {state.child_age_months} months"
        else:
            audience = f"kids' for age {state.child_age_months // 12} years"
    else:
        audience = (
            "men's" if state.department == "men"
            else "women's" if state.department == "women"
            else ""
        )
    option_label = "option" if total == 1 else "options"
    what = " ".join(item for item in (audience, description, option_label) if item)
    return f"I found {total} matching {what}. You can add a budget or size if you want to narrow them further."


def _gate_reply(state: SessionState) -> str:
    """Follow-up reply for the MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS gate when
    the matched turn came from the deterministic fast-path classifier.

    Real bug this fixes: fast-path replies ("Updated to pink — here's what
    matches") assume they're always showing refined results, which is true
    when refining an ongoing conversation but false if the fast-path match
    happens to be the shopper's very first message (e.g. opening with just
    "show me something pink") — the gate then suppresses all products, but
    the canned reply still claimed matches were shown. LLM-path replies
    aren't touched here; the prompt already makes those gate-aware.
    """
    known = []
    if state.wants_kids:
        known.append("shopping for a child")
    if state.occasion:
        known.append(f"the {state.occasion} occasion")
    if state.color_preference:
        known.append(f"the color {state.color_preference}")
    if state.style_descriptors:
        known.append(state.style_descriptors[-1])
    if state.category:
        known.append(state.category)
    if state.budget_max:
        known.append(f"a budget under Rs. {state.budget_max:,.0f}")
    if state.size:
        known.append(f"size {state.size}")

    acknowledgment = f"Got it — {', '.join(known)} noted. " if known else ""
    return acknowledgment + "Could you tell me a bit more — what occasion is this for, or what's your budget?"


def _department_gate_reply(state: SessionState) -> str:
    known = (
        state.category
        or state.occasion
        or (state.style_descriptors[-1] if state.style_descriptors else None)
    )
    prefix = f"I’ve noted {known}. " if known else ""
    return prefix + "Should I look in women’s or men’s clothing?"


def _has_any_extracted_field(diff: IntentExtractionResult) -> bool:
    """True if the LLM extracted ANYTHING usable this turn.

    Defense-in-depth against providers that set clarify=true while also
    asking a follow-up question alongside genuinely useful partial
    extraction — a real, observed Groq/Llama behavior. Only the true
    "nothing extractable" case (e.g. "hi") should skip merge + search.
    """
    return bool(
        diff.occasion
        or diff.category
        or diff.color_preference
        or diff.budget_max is not None
        or diff.size
        or diff.urgency_days is not None
        or diff.style_descriptors
        or diff.excluded
        or diff.excluded_styles
        or diff.wants_kids
        or diff.child_age_months is not None
        or diff.department is not None
    )


_UNSET = object()


def _build_filters(
    state: SessionState,
    effective_color: str | None,
    effective_size: str | None,
    effective_styles: list[str] | None = None,
    effective_occasion: str | None | object = _UNSET,
    effective_category: str | None | object = _UNSET,
    effective_budget: int | None | object = _UNSET,
) -> dict:
    """Project SessionState into the frontend's FilterChips shape.

    Takes the *effective* color/size actually applied to the returned
    results (post-relaxation), not just what the shopper asked for — a
    chip claiming "Color: Pink" while the grid shows red/purple/grey
    items would be actively misleading.

    Shows the *most recently* accumulated style descriptor, not the
    first — style_descriptors accumulates across a topic (see
    merge_session_state), and showing the oldest one forever left the
    chip stuck on whatever was said first even as the shopper's
    description evolved turn over turn.
    """
    styles = state.style_descriptors if effective_styles is None else effective_styles
    style = " ".join(dict.fromkeys(styles)).title() if styles else "All Styles"
    applied_occasion = state.occasion if effective_occasion is _UNSET else effective_occasion
    applied_category = state.category if effective_category is _UNSET else effective_category
    occasion = applied_occasion.title() if isinstance(applied_occasion, str) else "All Occasions"
    applied_budget = state.budget_max if effective_budget is _UNSET else effective_budget
    budget = f"Under Rs. {applied_budget:,.0f}" if isinstance(applied_budget, int) else "All Budgets"
    filters = {"style": style, "occasion": occasion, "budget": budget}
    filters["styles"] = styles
    if isinstance(applied_category, str):
        filters["category"] = applied_category.title()
    if effective_color:
        filters["color"] = effective_color.title()
    if effective_size:
        filters["size"] = effective_size
    if state.child_age_months is not None:
        months = state.child_age_months
        filters["age"] = (
            f"{months} months" if months < 24 else f"{months // 12} years"
        )
    return filters


@dataclass
class RelaxedSearch:
    result: ProductSearchResponse
    effective_color: str | None
    effective_size: str | None
    effective_styles: list[str]
    effective_occasion: str | None
    effective_category: str | None
    effective_budget: int | None
    dropped_occasion: bool
    dropped_budget: bool
    dropped_color: bool
    dropped_size: bool
    dropped_style: bool
    dropped_category: bool
    relaxed_formality: bool
    used_llm_fallback: bool
    exact_count: int


def _occasion_formality_floor(state: SessionState) -> int | None:
    """Cultural dress-code floor, modified only by explicit shopper intent."""
    occasion = (state.occasion or "").lower()
    styles = " ".join(state.style_descriptors).lower()
    exclusions = {value.lower() for value in state.excluded_styles}
    understated = any(
        term in styles for term in ("simple", "understated", "minimal", "not flashy")
    ) or bool(exclusions & {"embellished", "heavy embellishment"})
    if occasion in {"mehndi", "baraat"}:
        if "bridal" in styles and not understated:
            return BRIDAL
        return FORMAL if understated else PARTY
    if occasion in {"nikah", "walima", "engagement", "eid", "eid milan"}:
        return FORMAL
    return None


def _search_with_relax(
    products: list[Product], state: SessionState, page_size: int
) -> RelaxedSearch:
    """Return exact matches first, then fill the page with ranked near-matches.

    Audience, adult/child scope, exact child age, availability and negative
    evidence remain hard boundaries. Occasion, theme, dressiness and fields
    explicitly marked soft are relaxed one at a time. This preserves the best
    matches without turning a sparse exact set into an unnecessarily tiny grid.
    """
    exact_styles = state.style_descriptors
    hard = set(state.hard_constraints)
    soft = set(state.soft_preferences)

    def _run(
        category: str | None,
        occasion: str | None,
        color: str | None,
        styles: list[str],
        formality_floor: int | None,
        size: str | None,
        budget: int | None,
        occasion_as_signal: bool = False,
    ) -> ProductSearchResponse:
        return SearchService.search(
            products,
            query=" ".join(styles),
            category=category,
            occasion=occasion,
            color=color,
            size=size,
            max_price=budget,
            page=1,
            page_size=page_size,
            kids=state.wants_kids,
            child_age_months=state.child_age_months,
            department=state.department,
            require_all_keywords=bool(styles),
            semantic_query=state.semantic_query,
            min_formality=formality_floor,
            excluded_styles=state.excluded_styles,
            occasion_as_signal=occasion_as_signal,
            # Activewear is a functional product family, not a vague style
            # preference. Keep it strict so trousers/ordinary tees do not
            # leak into a gym-clothing request while other inferred styles
            # can still relax into near matches.
            strict_classification=(
                "style_descriptors" in hard
                or any(style.lower() == "activewear" for style in styles)
            ),
        )

    def _merge(
        primary: ProductSearchResponse,
        secondary: ProductSearchResponse,
    ) -> tuple[ProductSearchResponse, int]:
        items = list(primary.items)
        seen = {product.id for product in items}
        added = 0
        for product in secondary.items:
            if product.id in seen:
                continue
            items.append(product)
            seen.add(product.id)
            added += 1
            if len(items) >= page_size:
                break
        return ProductSearchResponse(
            items=items,
            total=len(items),
            page=1,
            page_size=page_size,
            has_more=False,
        ), added

    def _run_event_alternatives() -> ProductSearchResponse:
        # Search only culturally appropriate apparel families. A broad
        # occasion-only search can admit accessories (for example henna
        # stencils) or any product whose metadata happens to contain the
        # event word, which is not a useful garment alternative.
        unique: dict[str, Product] = {}
        alternatives = list(dict.fromkeys([
            *state.fallback_categories,
            *NEAR_MATCH_CATEGORIES.get((state.category or "").lower(), ()),
            *event_garments(occasion),
        ]))
        for alternative_category in alternatives:
            if alternative_category == state.category:
                continue
            category_result = _run(
                alternative_category,
                occasion,
                color,
                effective_styles,
                effective_formality,
                effective_size,
                effective_budget,
                occasion_as_signal=occasion_is_signal,
            )
            for product in category_result.items:
                unique.setdefault(product.id, product)
                if len(unique) >= page_size:
                    break
            if len(unique) >= page_size:
                break
        items = list(unique.values())
        return ProductSearchResponse(
            items=items,
            total=len(items),
            page=1,
            page_size=page_size,
            has_more=False,
        )

    occasion = state.occasion
    color = state.color_preference
    effective_size = state.size
    effective_budget = state.budget_max
    effective_styles = exact_styles
    effective_formality = _occasion_formality_floor(state)
    result = _run(
        state.category, occasion, color, effective_styles, effective_formality,
        effective_size, effective_budget,
    )
    exact_count = len(result.items)

    dropped_occasion = False
    dropped_category = False
    dropped_color = False
    dropped_style = False
    relaxed_formality = False
    used_llm_fallback = False
    effective_occasion = occasion
    effective_category = state.category
    occasion_is_signal = False
    formality_was_relaxed = False

    # Fill a sparse page in relevance tiers. Each tier is appended after the
    # previous one, so exact products always remain first.
    if len(result.items) < page_size and effective_styles and "style_descriptors" in soft:
        suggested_styles = state.fallback_styles
        candidate_styles = suggested_styles or []
        candidates = _run(
            state.category, occasion, color, candidate_styles, effective_formality,
            effective_size, effective_budget,
        )
        result, added = _merge(result, candidates)
        if added:
            effective_styles = candidate_styles
            dropped_style = True
            used_llm_fallback = bool(suggested_styles)

    # Event names are suitability signals rather than exclusive catalog tags.
    # Keep exact event evidence first, then admit same-intent products ranked
    # by event colors, garment families, formality and festive construction.
    if len(result.items) < page_size and occasion:
        occasion_is_signal = True
        candidates = _run(
            state.category, occasion, color, effective_styles, effective_formality,
            effective_size, effective_budget, occasion_as_signal=True,
        )
        result, added = _merge(result, candidates)
        if added:
            dropped_occasion = True
            effective_occasion = None

    if len(result.items) < page_size and effective_formality is not None and effective_formality > FORMAL:
        candidate_formality = effective_formality - 1
        formality_was_relaxed = True
        candidates = _run(
            state.category, occasion, color, effective_styles, candidate_formality,
            effective_size, effective_budget, occasion_as_signal=occasion_is_signal,
        )
        result, added = _merge(result, candidates)
        effective_formality = candidate_formality
        if added:
            relaxed_formality = True
            if occasion_is_signal:
                dropped_occasion = True
                effective_occasion = None

    if len(result.items) < page_size and color and "color_preference" in soft:
        candidates = _run(
            state.category, occasion, None, effective_styles, effective_formality,
            effective_size, effective_budget, occasion_as_signal=occasion_is_signal,
        )
        result, added = _merge(result, candidates)
        if added:
            color = None
            dropped_color = True

    if len(result.items) < page_size and effective_size and "size" in soft:
        candidates = _run(
            state.category, occasion, color, effective_styles, effective_formality,
            None, effective_budget, occasion_as_signal=occasion_is_signal,
        )
        result, added = _merge(result, candidates)
        if added:
            effective_size = None

    if len(result.items) < page_size and effective_budget is not None and "budget_max" in soft:
        candidates = _run(
            state.category, occasion, color, effective_styles, effective_formality,
            effective_size, None, occasion_as_signal=occasion_is_signal,
        )
        result, added = _merge(result, candidates)
        if added:
            effective_budget = None

    # A direct category remains first and strict. If it has zero inventory,
    # however, allow the curated near-match family so a request such as
    # "black sherwani" can still show black prince coats/achkans instead of
    # ending on an empty grid.
    if (
        len(result.items) < page_size
        and state.category
        and ("category" not in hard or result.total == 0)
    ):
        event_alternatives = _run_event_alternatives()
        result, added = _merge(result, event_alternatives)
        if added:
            dropped_category = True
            effective_category = None
            if occasion_is_signal:
                dropped_occasion = True
                effective_occasion = None
            if formality_was_relaxed:
                relaxed_formality = True

    return RelaxedSearch(
        result=result,
        effective_color=color,
        effective_size=effective_size,
        effective_styles=effective_styles,
        effective_occasion=effective_occasion,
        effective_category=effective_category,
        effective_budget=effective_budget,
        dropped_occasion=dropped_occasion,
        dropped_budget=effective_budget is None and state.budget_max is not None,
        dropped_color=dropped_color,
        dropped_size=effective_size is None and state.size is not None,
        dropped_style=dropped_style,
        dropped_category=dropped_category,
        relaxed_formality=relaxed_formality,
        used_llm_fallback=used_llm_fallback,
        exact_count=exact_count,
    )


def _relaxation_notice(relaxed: RelaxedSearch, state: SessionState) -> str | None:
    """Explain an alternative set in plain shopping language.

    The user should hear what was unavailable and what the cards actually
    contain. Internal phrases such as "relaxed product type" make the search
    mechanics visible but force the shopper to infer whether the displayed
    cards are tracksuits, waistcoats, or something else.
    """
    audience = (
        "kids'" if state.wants_kids
        else "men's" if state.department == "men"
        else "women's" if state.department == "women"
        else None
    )
    requested_details = [
        state.color_preference,
        audience,
        *state.style_descriptors,
        state.category,
        f"for {state.occasion}" if state.occasion else None,
    ]
    requested = " ".join(
        dict.fromkeys(value for value in requested_details if value)
    ) or "your exact request"

    found_categories: list[str] = []
    for product in relaxed.result.items:
        category = (
            extract_primary_garment(product.category or "")
            or extract_primary_garment(product.name)
        )
        if category and category not in found_categories:
            found_categories.append(category)
        if len(found_categories) == 3:
            break
    if found_categories:
        if len(found_categories) == 1:
            category_text = f"the {found_categories[0]} category"
        else:
            category_text = "the " + ", ".join(found_categories[:-1]) + f" and {found_categories[-1]} categories"
    else:
        category_text = "other product categories"

    count = len(relaxed.result.items)
    option_text = "one alternative" if count == 1 else f"{count} alternatives"
    apology = f"Sorry, I couldn't find any products matching {requested}."

    near_count = max(0, count - relaxed.exact_count)
    if relaxed.exact_count and near_count:
        exact_text = (
            "one exact match" if relaxed.exact_count == 1
            else f"{relaxed.exact_count} exact matches"
        )
        near_text = "one close alternative" if near_count == 1 else f"{near_count} close alternatives"
        return (
            f"I found {exact_text} and added {near_text} so you have more to compare. "
            "The closest matches are shown first."
        )

    if relaxed.dropped_category:
        return (
            f"{apology} I found {option_text} in {category_text} that match "
            "your remaining details, so you can try these instead."
        )
    if relaxed.used_llm_fallback:
        fallback_text = " and ".join(relaxed.effective_styles) or "the closest style"
        return (
            f"{apology} I used the next-best {fallback_text} direction and found "
            f"{option_text} that keep your confirmed details."
        )
    if relaxed.dropped_occasion:
        return (
            f"{apology} I found {option_text} in {category_text} that match "
            f"your other details, but I couldn't verify them specifically for {state.occasion}. "
            "You can try these instead."
        )
    if relaxed.relaxed_formality:
        return (
            f"{apology} I found {option_text} one dressiness tier lighter, while "
            f"still keeping them suitable for {state.occasion}."
        )

    dropped = []
    if relaxed.dropped_color:
        dropped.append(f"the {state.color_preference} color")
    if relaxed.dropped_size:
        dropped.append(f"size {state.size}")
    if relaxed.dropped_occasion:
        dropped.append(f"the {state.occasion} occasion")
    if relaxed.dropped_budget:
        dropped.append("your budget")
    if relaxed.dropped_style:
        dropped.append("the requested style")
    if relaxed.dropped_category:
        dropped.append(f"the {state.category} product type")
    if not dropped:
        return None
    dropped_text = dropped[0] if len(dropped) == 1 else ", ".join(dropped[:-1]) + f" and {dropped[-1]}"
    return (
        f"{apology} I found {option_text} after removing {dropped_text}. "
        "You can try these instead."
    )


class SessionService:
    """Orchestrates a single chat turn end-to-end."""

    def __init__(
        self,
        session_store: SessionStore,
        fallback_provider: FallbackIntentProvider,
        chat_repo: ChatRepository,
        events_repo: SessionEventRepository,
        query_cache_repo: QueryCacheRepository,
        brand_repo: BrandRepository,
        cache_service: ProductCacheService,
        llm_first_intent_enabled: bool = True,
        live_validator: LiveProductValidationService | None = None,
        live_shortlist_size: int = 40,
    ):
        self._session_store = session_store
        self._fallback_provider = fallback_provider
        self._chat_repo = chat_repo
        self._events_repo = events_repo
        self._query_cache_repo = query_cache_repo
        self._brand_repo = brand_repo
        self._cache_service = cache_service
        self._llm_first_intent_enabled = llm_first_intent_enabled
        self._live_validator = live_validator
        self._live_shortlist_size = max(DEFAULT_PAGE_SIZE, live_shortlist_size)

    async def handle_turn(
        self,
        session_id: str | None,
        device_id: UUID | None,
        text: str,
        department: str | None = None,
        client_state: SessionState | None = None,
    ) -> ChatTurnResponse:
        turn_started = perf_counter()
        session_id = session_id or str(uuid4())
        stored_state = await self._session_store.get(session_id)
        current_state = stored_state or client_state or SessionState()
        # Rehydrate sessions created before category became structured. Old
        # garment words lived inside style_descriptors and otherwise keep
        # colliding with every later search.
        legacy_category = current_state.category or extract_primary_garment(
            " ".join(current_state.style_descriptors)
        )
        if legacy_category or current_state.style_descriptors:
            current_state = current_state.model_copy(update={
                "category": legacy_category,
                "style_descriptors": without_garment_descriptors(
                    current_state.style_descriptors
                ),
            })
        if current_state.occasion and not is_known_event(current_state.occasion):
            recovered = extract_classification_request(current_state.occasion)
            recovered_styles = [
                value for value in (recovered.formality, recovered.tradition) if value
            ]
            current_state = current_state.model_copy(update={
                "occasion": None,
                "style_descriptors": list(dict.fromkeys([
                    *current_state.style_descriptors,
                    *recovered_styles,
                ])),
            })
        # Onboarding seeds the audience once. An explicit conversational
        # clarification can then overwrite it and must survive later turns.
        if department is not None and current_state.department is None:
            current_state = current_state.model_copy(update={"department": department})
        last_results = await self._session_store.get_last_results(session_id)

        await self._chat_repo.add_message(session_id, "user", text, device_id)

        show_more = False
        intent_started = perf_counter()
        taxonomy_request = extract_classification_request(text)
        fast_match = (
            classify(text, current_state, last_results)
            if (
                is_control_message(text)
                or taxonomy_request.activewear
                or (
                    taxonomy_request.tradition
                    and extract_primary_garment(text) is None
                )
                or not self._llm_first_intent_enabled
            )
            else None
        )
        if fast_match is not None:
            diff = fast_match.diff
            show_more = fast_match.show_more
            turn_type = "fast_path"
        else:
            diff = await self._extract_intent(text, current_state)
            turn_type = "llm_extraction"
        if diff.operation == "show_more":
            show_more = True
        intent_ms = (perf_counter() - intent_started) * 1000

        # Deterministic parsing is a guardrail, not a second intent engine.
        # The LLM owns fields that require semantics and cultural context.
        # Code only confirms facts that must never be guessed or relaxed.
        llm_turn = turn_type == "llm_extraction"
        if is_kids_request(text):
            diff.wants_kids = True
        explicit_department = extract_department(text.lower())
        department_changed = bool(
            explicit_department
            and current_state.department
            and explicit_department != current_state.department
        )
        if explicit_department is not None:
            diff.department = explicit_department

        # LLM-inferred styling enriches ranking, but cannot become a strict
        # all-keywords gate unless the shopper actually used that wording.
        if "style_descriptors" in diff.hard_constraints:
            normalized_text = re.sub(r"[^a-z0-9]+", " ", text.lower())
            explicitly_stated = any(
                re.sub(r"[^a-z0-9]+", " ", style.lower()).strip() in normalized_text
                for style in diff.style_descriptors
                if style.strip()
            )
            if not explicitly_stated:
                diff.hard_constraints = [
                    field for field in diff.hard_constraints
                    if field != "style_descriptors"
                ]
                if diff.style_descriptors and "style_descriptors" not in diff.soft_preferences:
                    diff.soft_preferences.append("style_descriptors")

        if llm_turn:
            # Never replace the model's resolved meaning with literal lookup
            # output. This is what lets misspellings, Roman Urdu, vibes and
            # culturally phrased requests map to canonical catalog concepts.
            resolved_event = diff.occasion
            resolved_category = diff.category
            broad_request = extract_classification_request(text)
            if (
                (broad_request.tradition or broad_request.activewear)
                and extract_primary_garment(text) is None
            ):
                # A provider may translate "western wear" into one guessed
                # category such as co-ords. Keep the shopper's broad family
                # intact so shirts, tops, dresses, jeans, skirts and trousers
                # can all compete by relevance.
                resolved_category = None
                diff.category = None
                family_style = (
                    "activewear" if broad_request.activewear
                    else broad_request.tradition
                )
                if family_style:
                    diff.style_descriptors = [
                        style for style in diff.style_descriptors
                        if not (
                            extract_classification_request(style).tradition == family_style
                            or (
                                family_style == "activewear"
                                and extract_classification_request(style).activewear
                            )
                        )
                    ]
                    diff.style_descriptors.append(family_style)
            diff.style_descriptors = without_garment_descriptors(
                diff.style_descriptors
            )
            if (
                resolved_event
                and resolved_event.lower() in {"independence day", "pakistan day"}
                and not re.search(r"\b(?:green|white)\b", text, re.IGNORECASE)
            ):
                # The model may explain the visual meaning of a national-day
                # theme as "green and white palette". That belongs in semantic
                # ranking, not an all-keywords gate, unless the shopper actually
                # stated those colors.
                diff.style_descriptors = [
                    style for style in diff.style_descriptors
                    if not re.search(
                        r"\b(?:independence|pakistan|patriotic|green|white|palette)\b",
                        style,
                        re.IGNORECASE,
                    )
                ]
            daaku_fallback = False
        else:
            resolved_event = extract_event(text)
            if resolved_event is not None:
                diff.occasion = resolved_event
            elif diff.occasion and not is_known_event(diff.occasion):
                diff.occasion = None
            explicit_color = extract_color(text)
            if explicit_color is not None:
                diff.color_preference = explicit_color
            resolved_category = extract_primary_garment(text)
            daaku_fallback = bool(
                resolved_category is None
                and re.search(r"\b(?:daaku|daku|bandit)\b", text, re.IGNORECASE)
            )
            if daaku_fallback:
                resolved_category = "kurta"
            diff.category = resolved_category
            diff.style_descriptors = without_garment_descriptors(
                ground_style_descriptors(text, diff.style_descriptors)
            )

        explicit_budget = extract_budget_max(text)
        if explicit_budget is not None:
            diff.budget_max = explicit_budget
        explicit_size = extract_size(text)
        if explicit_size is not None:
            diff.size = explicit_size
        if diff.remove_styles:
            removed_style_keys = {style.lower().strip() for style in diff.remove_styles}
            diff.style_descriptors = [
                style for style in diff.style_descriptors
                if style.lower().strip() not in removed_style_keys
            ]
        explicit_exclusions = extract_excluded_styles(text)
        if explicit_exclusions:
            diff.excluded_styles = list(dict.fromkeys([
                *diff.excluded_styles,
                *explicit_exclusions,
            ]))
            # A negative refinement must also remove the old positive signal
            # from both state and semantic reranking text.
            if "embellished" in explicit_exclusions:
                diff.remove_styles = list(dict.fromkeys([
                    *diff.remove_styles, "embroidered", "embellished",
                ]))
            semantic_base = diff.semantic_query or current_state.semantic_query or ""
            for excluded in explicit_exclusions:
                semantic_base = re.sub(
                    rf"\b{re.escape(excluded)}\b", " ", semantic_base,
                    flags=re.IGNORECASE,
                )
            diff.semantic_query = " ".join(semantic_base.split())

        validated_categories = []
        for suggestion in diff.fallback_categories:
            category = extract_primary_garment(suggestion)
            if category and category != (diff.category or current_state.category):
                validated_categories.append(category)
        diff.fallback_categories = list(dict.fromkeys(validated_categories))[:5]

        validated_styles = []
        for suggestion in diff.fallback_styles:
            canonical = re.sub(r"\s+", " ", suggestion.lower().strip())
            if canonical in VALID_FALLBACK_STYLES:
                validated_styles.append(canonical)
                continue
            validated_styles.extend(
                style for style in ground_style_descriptors(suggestion, [suggestion])
                if style.lower() in VALID_FALLBACK_STYLES
            )
        diff.fallback_styles = list(dict.fromkeys(validated_styles))[:5]
        if daaku_fallback:
            diff.style_descriptors = [
                style for style in diff.style_descriptors
                if style.lower() not in {"daaku", "daku", "bandit"}
            ]
        child_age_months = extract_child_age_months(text)
        if child_age_months is not None:
            diff.child_age_months = child_age_months
            # Groq sometimes duplicates "2 years old" into size="2 years".
            # Age is handled by the stricter range filter; leaving the duplicate
            # in the generic size field makes relaxation claim that age was
            # dropped even though it was correctly retained.
            if diff.size and any(
                start <= child_age_months <= end
                for start, end in extract_age_ranges([diff.size])
            ):
                diff.size = None

        await self._events_repo.log_event(session_id, f"turn_{turn_type}", device_id)

        if diff.clarify and not _has_any_extracted_field(diff):
            clarification_reply = diff.assistant_reply.strip() or (
                "Could you tell me what kind of clothing you need, and whether I should "
                "search women's or men's collections?"
            )
            await self._chat_repo.add_message(
                session_id, "assistant", clarification_reply, device_id
            )
            return ChatTurnResponse(
                session_id=session_id,
                reply=clarification_reply,
                session_state=current_state,
                filters=_build_filters(current_state, current_state.color_preference, current_state.size),
                products=ProductSearchResponse(
                    items=last_results,
                    total=len(last_results),
                    page=1,
                    page_size=DEFAULT_PAGE_SIZE,
                    has_more=False,
                ),
                turn_type=turn_type,
            )

        category_changed = bool(
            resolved_category and resolved_category != current_state.category
        )
        occasion_changed = bool(
            resolved_event and resolved_event != current_state.occasion
        )
        standalone_kids_topic = bool(
            diff.wants_kids is True
            and resolved_category is None
            and _KIDS_TOPIC_PATTERN.search(text)
        )
        starts_new_topic = bool(
            diff.operation == "new_search"
            or (category_changed and not _CATEGORY_REFINEMENT_PATTERN.search(text))
            or (occasion_changed and not _OCCASION_REFINEMENT_PATTERN.search(text))
            or standalone_kids_topic
        )
        merge_base = current_state
        if starts_new_topic:
            # Independent searches retain stable audience/brand scope. Child
            # scope is also stable until the shopper explicitly asks for an
            # adult: a product-only follow-up such as "pink shirts" must not
            # turn a two-year-old daughter's search into adult womenswear.
            retained_hard = [
                field for field in current_state.hard_constraints
                if field in {"department", "child_age_months"}
            ]
            merge_base = SessionState(
                department=current_state.department,
                brands=current_state.brands,
                wants_kids=current_state.wants_kids,
                child_age_months=current_state.child_age_months,
                hard_constraints=retained_hard,
            )

        new_state = merge_session_state(merge_base, diff)
        if diff.wants_kids is False:
            new_state = new_state.model_copy(update={
                "wants_kids": False,
                "child_age_months": None,
            })
        if department_changed:
            department_updates = {
                "style_descriptors": _styles_after_department_switch(new_state.style_descriptors),
                "category": resolved_category,
                "size": None,
            }
            # An adult audience switch leaves any previous kids topic. A
            # child-specific switch ("for my son/daughter") must preserve the
            # newly confirmed kids mode and exact age instead.
            if diff.wants_kids is not True:
                department_updates.update({
                    "wants_kids": False,
                    "child_age_months": None,
                })
            new_state = new_state.model_copy(update=department_updates)

        if new_state.department is None and not new_state.wants_kids:
            reply = _department_gate_reply(new_state)
            await self._session_store.set(session_id, new_state)
            await self._chat_repo.add_message(session_id, "assistant", reply, device_id)
            return ChatTurnResponse(
                session_id=session_id,
                reply=reply,
                session_state=new_state,
                filters=_build_filters(new_state, new_state.color_preference, new_state.size),
                products=ProductSearchResponse(
                    items=[], total=0, page=1, page_size=DEFAULT_PAGE_SIZE, has_more=False
                ),
                turn_type=turn_type,
            )

        # Don't show a grab-bag on a vague query — ask another follow-up
        # instead until enough is known to narrow well. Once the threshold
        # is crossed, known signals persist across turns (merge_session_state
        # accumulates/overwrites, never silently clears), so this never
        # re-hides results already being shown.
        if (
            _known_signal_count(new_state) < MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS
            and not is_known_event(new_state.occasion)
            and new_state.category is None
            and not new_state.wants_kids
            and not any((
                extract_classification_request(" ".join(new_state.style_descriptors)).formality,
                extract_classification_request(" ".join(new_state.style_descriptors)).tradition,
                extract_classification_request(" ".join(new_state.style_descriptors)).activewear,
            ))
            and not department_changed
        ):
            # Fast-path replies ("Updated to pink") assume they're always
            # showing refined results — true when refining an ongoing
            # conversation, false if this fast-path match happens to be the
            # very first message. The LLM path's reply is already gate-aware
            # by prompt design, so only fast-path turns need overriding here.
            gate_reply = (
                _gate_reply(new_state)
                if turn_type == "fast_path" or not diff.assistant_reply.strip()
                else diff.assistant_reply
            )
            await self._session_store.set(session_id, new_state)
            await self._chat_repo.add_message(
                session_id, "assistant", gate_reply, device_id
            )
            return ChatTurnResponse(
                session_id=session_id,
                reply=gate_reply,
                session_state=new_state,
                filters=_build_filters(new_state, new_state.color_preference, new_state.size),
                products=ProductSearchResponse(
                    items=[], total=0, page=1, page_size=DEFAULT_PAGE_SIZE, has_more=False
                ),
                turn_type=turn_type,
            )

        catalog_started = perf_counter()
        all_products = await self._collect_candidate_products(new_state)
        catalog_ms = (perf_counter() - catalog_started) * 1000
        # Retrieval builds a bounded backfill shortlist. The UI still receives
        # only DEFAULT_PAGE_SIZE live-verified cards; no chat turn downloads or
        # serializes the entire multi-brand catalog.
        page_size = (
            self._live_shortlist_size
            if self._live_validator is not None
            else DEFAULT_PAGE_SIZE
        )
        # Regex-heavy ranking over a large multi-brand snapshot is CPU work.
        # Keep it off the asyncio loop so chat/search cannot freeze health,
        # wishlist, or other users' requests while one result set is ranked.
        search_started = perf_counter()
        if len(all_products) >= 1000:
            relaxed = await run_in_threadpool(
                _search_with_relax, all_products, new_state, page_size
            )
        else:
            relaxed = _search_with_relax(all_products, new_state, page_size)
        result = relaxed.result
        search_ms = (perf_counter() - search_started) * 1000

        live_ms = 0.0
        live_unavailable = 0
        live_failed = 0
        if self._live_validator is not None and result.items:
            live_started = perf_counter()
            active_brands = await self._brand_repo.get_all_active()
            allowed_domains = {brand.domain for brand in active_brands}
            live = await self._live_validator.validate(
                result.items,
                allowed_domains,
                DEFAULT_PAGE_SIZE,
            )
            live_unavailable = live.unavailable
            live_failed = live.failed
            # Reapply every hard filter and evidence rule to current Shopify
            # metadata. A product edited since the cached shortlist was built
            # cannot remain merely because its stale copy used to match.
            if live.products:
                relaxed = _search_with_relax(
                    live.products, new_state, DEFAULT_PAGE_SIZE
                )
                result = relaxed.result
            else:
                result = ProductSearchResponse(
                    items=[], total=0, page=1,
                    page_size=DEFAULT_PAGE_SIZE, has_more=False,
                )
            live_ms = (perf_counter() - live_started) * 1000

        # A specific-enough request that still comes back empty is a real
        # catalog miss, not vagueness — say so plainly instead of leaving
        # the LLM's speculatively-written reply (written before the search
        # ran) implying results that aren't actually there. Same idea if a
        # filter had to be silently relaxed to avoid an empty grid — the
        # reply must reflect what's actually shown, not what was asked for.
        if result.total == 0 and live_failed > 0 and live_unavailable == 0:
            reply = (
                "I found possible matches, but I couldn't verify their live stock with "
                "the stores just now. Please try again in a moment."
            )
        elif result.total == 0:
            reply = _no_results_reply(new_state)
        else:
            provider_reply = diff.assistant_reply.strip()
            reply = _relaxation_notice(relaxed, new_state) or (
                _results_reply(new_state, result.total)
                if turn_type == "fast_path" or new_state.wants_kids or "?" in provider_reply
                else provider_reply or _results_reply(new_state, result.total)
            )

        persistence_started = perf_counter()
        await self._session_store.set(session_id, new_state)
        await self._session_store.set_last_results(session_id, result.items)
        await self._chat_repo.add_message(session_id, "assistant", reply, device_id)
        persistence_ms = (perf_counter() - persistence_started) * 1000
        timing_logger.info(
            "session_turn_timing turn_type=%s total_ms=%.1f intent_ms=%.1f "
            "catalog_ms=%.1f search_ms=%.1f live_ms=%.1f persistence_ms=%.1f "
            "candidates=%d results=%d live_unavailable=%d live_failed=%d",
            turn_type,
            (perf_counter() - turn_started) * 1000,
            intent_ms,
            catalog_ms,
            search_ms,
            live_ms,
            persistence_ms,
            len(all_products),
            result.total,
            live_unavailable,
            live_failed,
        )

        return ChatTurnResponse(
            session_id=session_id,
            reply=reply,
            session_state=new_state,
            filters=_build_filters(
                new_state,
                relaxed.effective_color,
                relaxed.effective_size,
                effective_styles=relaxed.effective_styles,
                effective_occasion=relaxed.effective_occasion,
                effective_category=relaxed.effective_category,
                effective_budget=relaxed.effective_budget,
            ),
            products=result,
            turn_type=turn_type,
        )

    async def reset_session(self, session_id: str) -> ChatTurnResponse:
        """Clear a session's state/results back to fresh — the only reliable
        way to honor "Clear All", since merge_session_state only overwrites
        fields on new extraction and never clears one on request.

        department is preserved — it's an onboarding-level identity
        preference (like size), not a conversational search filter, so
        "Clear All" shouldn't silently widen the catalog back to all
        departments.
        """
        current_state = await self._session_store.get(session_id) or SessionState()
        fresh_state = SessionState(department=current_state.department)
        reply = "I've cleared the current filters — tell me what you're looking for!"

        await self._session_store.set(session_id, fresh_state)
        await self._session_store.set_last_results(session_id, [])
        await self._chat_repo.add_message(session_id, "assistant", reply, None)

        return ChatTurnResponse(
            session_id=session_id,
            reply=reply,
            session_state=fresh_state,
            filters=_build_filters(fresh_state, None, None),
            products=ProductSearchResponse(
                items=[], total=0, page=1, page_size=DEFAULT_PAGE_SIZE, has_more=False
            ),
            turn_type="fast_path",
        )

    async def _extract_intent(
        self, text: str, current_state: SessionState
    ) -> IntentExtractionResult:
        normalized = text.strip().lower()
        context_key = json.dumps(
            current_state.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        cache_key = f"{INTENT_CACHE_VERSION}|{normalized}|{context_key}"
        cached = await self._query_cache_repo.get_cached(cache_key)
        if cached:
            return IntentExtractionResult.model_validate(cached)

        try:
            diff = await self._fallback_provider.extract(text, current_state)
        except ExternalServiceError:
            logger.error("Both LLM providers failed; falling back to a clarifying reply")
            return IntentExtractionResult(
                assistant_reply=(
                    "I'm having trouble understanding right now — could you try "
                    "rephrasing, or tell me the occasion and budget you have in mind?"
                ),
                clarify=True,
            )

        await self._query_cache_repo.cache_extraction(
            cache_key, diff.model_dump(mode="json")
        )
        return diff

    async def _collect_candidate_products(self, state: SessionState) -> list[Product]:
        brands = await self._brand_repo.get_all_active(department=state.department)
        target_brands = [
            b
            for b in brands
            if b.slug not in state.excluded
            and (not state.brands or b.slug in state.brands)
        ]

        # Cold catalogs used to refresh every brand sequentially, making a
        # simple first search feel frozen. Limit concurrency to four storefronts
        # at a time to reduce latency without hammering Shopify.
        semaphore = asyncio.Semaphore(4)

        async def fetch_brand(brand):
            async with semaphore:
                products = await self._cache_service.get_or_refresh(brand.slug, brand.domain)
            if products:
                # A gendered brand supplies a reliable fallback when individual
                # Shopify products omit audience tags. Unisex brands retain
                # product-level metadata so mixed catalogs can still be filtered.
                effective_department = KNOWN_BRAND_DEPARTMENTS.get(
                    brand.slug, brand.department
                )
                if effective_department in {"men", "women"}:
                    # These Product objects are the worker's decoded cache.
                    # Enrich missing audience metadata once instead of cloning
                    # thousands of models again on every search turn.
                    for product in products:
                        if product.department is None:
                            product.department = effective_department
                return products
            return []

        brand_products = await asyncio.gather(*(fetch_brand(brand) for brand in target_brands))
        all_products = [product for products in brand_products for product in products]
        return all_products
