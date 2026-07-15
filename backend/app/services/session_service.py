"""Chat turn orchestration: fast-path -> query cache -> LLM -> merge -> search."""

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.errors import ExternalServiceError
from app.llm.fallback import FallbackIntentProvider
from app.nlp.diff_merge import merge_session_state
from app.nlp.fast_path_classifier import classify, is_kids_request
from app.repositories.brand_repo import BrandRepository
from app.repositories.chat_repo import ChatRepository
from app.repositories.events_repo import SessionEventRepository
from app.repositories.query_cache_repo import QueryCacheRepository
from app.schemas.product import Product, ProductSearchResponse
from app.schemas.session import ChatTurnResponse, IntentExtractionResult, SessionState
from app.services.product_cache_service import ProductCacheService
from app.services.search_service import SearchService
from app.session_store.base import SessionStore

logger = logging.getLogger(__name__)

MIN_RESULTS_BEFORE_RELAX = 10
SHOW_MORE_PAGE_SIZE = 40
DEFAULT_PAGE_SIZE = 20

# How many of {occasion, budget, color/style/garment, size} must be known
# before showing products at all, rather than asking another follow-up.
# Once this many signals are known they persist across turns (merge_session_state
# accumulates/overwrites, never silently clears), so this only gates the
# *first* couple of turns on a vague query — it never re-hides results
# already being shown.
MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS = 2


def _known_signal_count(state: SessionState) -> int:
    return sum([
        bool(state.occasion),
        state.budget_max is not None,
        bool(state.color_preference or state.style_descriptors),
        bool(state.size),
        state.wants_kids,
    ])


def _no_results_reply(state: SessionState) -> str:
    """A good-mannered reply for a genuine miss — the shopper asked for
    something specific enough that nothing in the current catalog matches
    it, rather than the query just being too vague to narrow (that case
    never reaches a search at all, see MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS)."""
    described = state.style_descriptors[-1] if state.style_descriptors else None
    what = described or (state.occasion.title() if state.occasion else "that")
    return (
        f"I'm sorry, we don't currently have anything matching {what} in our "
        "catalog. Would you like to try a different style, color, or budget?"
    )


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
    if state.budget_max:
        known.append(f"a budget under Rs. {state.budget_max:,.0f}")
    if state.size:
        known.append(f"size {state.size}")

    acknowledgment = f"Got it — {', '.join(known)} noted. " if known else ""
    return acknowledgment + "Could you tell me a bit more — what occasion is this for, or what's your budget?"


def _has_any_extracted_field(diff: IntentExtractionResult) -> bool:
    """True if the LLM extracted ANYTHING usable this turn.

    Defense-in-depth against providers that set clarify=true while also
    asking a follow-up question alongside genuinely useful partial
    extraction — a real, observed Groq/Llama behavior. Only the true
    "nothing extractable" case (e.g. "hi") should skip merge + search.
    """
    return bool(
        diff.occasion
        or diff.color_preference
        or diff.budget_max is not None
        or diff.size
        or diff.urgency_days is not None
        or diff.style_descriptors
        or diff.excluded
        or diff.wants_kids
    )


def _build_filters(
    state: SessionState, effective_color: str | None, effective_size: str | None
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
    style = state.style_descriptors[-1].title() if state.style_descriptors else "All Styles"
    occasion = state.occasion.title() if state.occasion else "All Occasions"
    budget = f"Under Rs. {state.budget_max:,.0f}" if state.budget_max else "All Budgets"
    filters = {"style": style, "occasion": occasion, "budget": budget}
    if effective_color:
        filters["color"] = effective_color.title()
    if effective_size:
        filters["size"] = effective_size
    return filters


@dataclass
class RelaxedSearch:
    result: ProductSearchResponse
    effective_color: str | None
    effective_size: str | None
    dropped_occasion: bool
    dropped_budget: bool
    dropped_color: bool
    dropped_size: bool


def _search_with_relax(
    products: list[Product], state: SessionState, page_size: int
) -> RelaxedSearch:
    """Run search, progressively relaxing the most restrictive filters if
    results are too thin — never return a sparse grid when a looser match
    exists. Order: budget, then occasion, then color, then size — each
    step relaxes exactly one *additional* filter and only if the result
    is still thin, carrying forward whatever was already relaxed.

    Real bug this fixes: the color/size step used to unconditionally
    replace the result with a fully-unfiltered search (dropping occasion
    and budget too, even if those were never re-checked) any time color
    or size were merely *set*, regardless of whether the occasion+budget-
    relaxed result had already cleared the threshold. A shopper asking
    for "pink wedding wear" would see the reply claim "updated to pink"
    while the actual grid silently dropped the color filter entirely and
    showed red/purple/grey items instead.
    """
    query = " ".join(state.style_descriptors)

    def _run(
        occasion: str | None, max_price: float | None, color: str | None, size: str | None
    ) -> ProductSearchResponse:
        return SearchService.search(
            products,
            query=query,
            occasion=occasion,
            color=color,
            size=size,
            max_price=max_price,
            page=1,
            page_size=page_size,
            kids=state.wants_kids,
        )

    occasion, budget, color, size = state.occasion, state.budget_max, state.color_preference, state.size
    result = _run(occasion, budget, color, size)

    if result.total < MIN_RESULTS_BEFORE_RELAX and budget is not None:
        budget = None
        result = _run(occasion, budget, color, size)

    if result.total < MIN_RESULTS_BEFORE_RELAX and occasion is not None:
        occasion = None
        result = _run(occasion, budget, color, size)

    if result.total < MIN_RESULTS_BEFORE_RELAX and color is not None:
        color = None
        result = _run(occasion, budget, color, size)

    if result.total < MIN_RESULTS_BEFORE_RELAX and size is not None:
        size = None
        result = _run(occasion, budget, color, size)

    return RelaxedSearch(
        result=result,
        effective_color=color,
        effective_size=size,
        dropped_occasion=state.occasion is not None and occasion is None,
        dropped_budget=state.budget_max is not None and budget is None,
        dropped_color=state.color_preference is not None and color is None,
        dropped_size=state.size is not None and size is None,
    )


def _relaxation_notice(relaxed: RelaxedSearch, state: SessionState) -> str | None:
    """An honest reply when a filter had to be dropped to avoid an
    empty/sparse grid — never let the LLM's speculatively-written reply
    (written before the search ran) claim a match that isn't there."""
    dropped = []
    if relaxed.dropped_color:
        dropped.append(f"the {state.color_preference} color")
    if relaxed.dropped_size:
        dropped.append(f"size {state.size}")
    if relaxed.dropped_occasion:
        dropped.append(f"the {state.occasion} occasion")
    if relaxed.dropped_budget:
        dropped.append("your budget")
    if not dropped:
        return None
    dropped_text = dropped[0] if len(dropped) == 1 else ", ".join(dropped[:-1]) + f" and {dropped[-1]}"
    return (
        f"We don't have quite enough exact matches, so I've relaxed {dropped_text} "
        "to show you the closest options instead."
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
    ):
        self._session_store = session_store
        self._fallback_provider = fallback_provider
        self._chat_repo = chat_repo
        self._events_repo = events_repo
        self._query_cache_repo = query_cache_repo
        self._brand_repo = brand_repo
        self._cache_service = cache_service

    async def handle_turn(
        self,
        session_id: str | None,
        device_id: UUID | None,
        text: str,
        department: str | None = None,
    ) -> ChatTurnResponse:
        session_id = session_id or str(uuid4())
        current_state = await self._session_store.get(session_id) or SessionState()
        # Department comes directly from onboarding, not the LLM/fast-path
        # diff pipeline — explicit overwrite here, separate from merge_session_state.
        if department is not None:
            current_state = current_state.model_copy(update={"department": department})
        last_results = await self._session_store.get_last_results(session_id)

        await self._chat_repo.add_message(session_id, "user", text, device_id)

        show_more = False
        fast_match = classify(text, current_state, last_results)
        if fast_match is not None:
            diff = fast_match.diff
            show_more = fast_match.show_more
            turn_type = "fast_path"
        else:
            diff = await self._extract_intent(text, current_state)
            turn_type = "llm_extraction"

        # Deterministic, code-level check regardless of which path handled
        # the rest of the extraction — the LLM doesn't reliably recognize
        # "shopping for a child" on its own (see is_kids_request). Only ever
        # set True here, never False, so an unrelated later turn in the same
        # kids-shopping conversation doesn't reset the persisted signal.
        if is_kids_request(text):
            diff.wants_kids = True

        await self._events_repo.log_event(session_id, f"turn_{turn_type}", device_id)

        if diff.clarify and not _has_any_extracted_field(diff):
            await self._chat_repo.add_message(
                session_id, "assistant", diff.assistant_reply, device_id
            )
            return ChatTurnResponse(
                session_id=session_id,
                reply=diff.assistant_reply,
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

        new_state = merge_session_state(current_state, diff)

        # Don't show a grab-bag on a vague query — ask another follow-up
        # instead until enough is known to narrow well. Once the threshold
        # is crossed, known signals persist across turns (merge_session_state
        # accumulates/overwrites, never silently clears), so this never
        # re-hides results already being shown.
        if _known_signal_count(new_state) < MIN_SIGNALS_BEFORE_SHOWING_PRODUCTS:
            # Fast-path replies ("Updated to pink") assume they're always
            # showing refined results — true when refining an ongoing
            # conversation, false if this fast-path match happens to be the
            # very first message. The LLM path's reply is already gate-aware
            # by prompt design, so only fast-path turns need overriding here.
            gate_reply = _gate_reply(new_state) if turn_type == "fast_path" else diff.assistant_reply
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

        all_products = await self._collect_candidate_products(new_state)
        page_size = SHOW_MORE_PAGE_SIZE if show_more else DEFAULT_PAGE_SIZE
        relaxed = _search_with_relax(all_products, new_state, page_size)
        result = relaxed.result

        # A specific-enough request that still comes back empty is a real
        # catalog miss, not vagueness — say so plainly instead of leaving
        # the LLM's speculatively-written reply (written before the search
        # ran) implying results that aren't actually there. Same idea if a
        # filter had to be silently relaxed to avoid an empty grid — the
        # reply must reflect what's actually shown, not what was asked for.
        if result.total == 0:
            reply = _no_results_reply(new_state)
        else:
            reply = _relaxation_notice(relaxed, new_state) or diff.assistant_reply

        await self._session_store.set(session_id, new_state)
        await self._session_store.set_last_results(session_id, result.items)
        await self._chat_repo.add_message(session_id, "assistant", reply, device_id)

        return ChatTurnResponse(
            session_id=session_id,
            reply=reply,
            session_state=new_state,
            filters=_build_filters(new_state, relaxed.effective_color, relaxed.effective_size),
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
        cached = await self._query_cache_repo.get_cached(normalized)
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
            normalized, diff.model_dump(mode="json")
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

        all_products: list[Product] = []
        for brand in target_brands:
            products = await self._cache_service.get_or_refresh(brand.slug, brand.domain)
            if products:
                all_products.extend(products)
        return all_products
