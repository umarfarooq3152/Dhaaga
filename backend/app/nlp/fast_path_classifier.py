"""Deterministic, pure fast-path classifier for common chat refinements.

Runs BEFORE the query-intent cache or any LLM call, so the most common
follow-up turns ("cheaper", "show more", ...) never pay LLM latency/cost.
Returns None when nothing matches, so the caller falls through to the
cache/LLM path.
"""

import math
from dataclasses import dataclass

from app.schemas.product import Product
from app.schemas.session import IntentExtractionResult, SessionState

KNOWN_COLORS = [
    "red", "blue", "green", "black", "white", "gold", "maroon", "emerald",
    "pink", "yellow", "purple", "orange", "beige", "navy", "teal",
    "lavender", "mint", "rust", "coral", "ivory", "mustard", "peach",
    "turquoise", "lilac", "crimson", "burgundy",
]

CHEAPER_PHRASES = ["cheaper", "less expensive", "lower budget", "more affordable", "budget option"]
MORE_FORMAL_PHRASES = ["more formal", "dressier", "fancier"]
MORE_CASUAL_PHRASES = ["more casual", "less formal", "simpler"]
DIFFERENT_BRAND_PHRASES = ["different brand", "another brand", "other brands"]
SHOW_MORE_PHRASES = ["show more", "more options", "more results", "see more"]

BUDGET_REDUCTION_FACTOR = 0.9
PRICE_ROUNDING = 1000


@dataclass
class FastPathMatch:
    """Result of a matched fast-path pattern.

    `diff` is merged into session state exactly like an LLM-extracted diff.
    `show_more` signals the caller to widen this turn's page size WITHOUT
    persisting any session-state change (there's no page-tracking field in
    SessionState — "show more" simply asks for a bigger single response
    rather than true cursor pagination, a deliberate MVP simplification).
    """

    diff: IntentExtractionResult
    show_more: bool = False


def _empty_diff(assistant_reply: str) -> IntentExtractionResult:
    return IntentExtractionResult(assistant_reply=assistant_reply, clarify=False)


def classify(
    text: str, current: SessionState, last_results: list[Product]
) -> FastPathMatch | None:
    """Try to match `text` against known fast-path refinement patterns.

    Args:
        text: The user's message for this turn.
        current: Current session state (used to compute relative changes).
        last_results: Products shown in the previous turn (used to compute
            "cheaper" thresholds and the dominant brand for "different brand").

    Returns:
        A FastPathMatch if a pattern matched, else None (fall through to
        query-intent cache / LLM extraction).
    """
    lower = text.lower().strip()

    if any(phrase in lower for phrase in CHEAPER_PHRASES):
        return _match_cheaper(last_results)

    if any(phrase in lower for phrase in MORE_FORMAL_PHRASES):
        return _match_style_shift(add="formal", remove="casual")

    if any(phrase in lower for phrase in MORE_CASUAL_PHRASES):
        return _match_style_shift(add="casual", remove="formal")

    color_match = next((c for c in KNOWN_COLORS if c in lower), None)
    if color_match and _is_color_only_message(lower, color_match):
        return _match_color(color_match)

    if any(phrase in lower for phrase in DIFFERENT_BRAND_PHRASES):
        return _match_different_brand(last_results)

    if any(phrase in lower for phrase in SHOW_MORE_PHRASES):
        return FastPathMatch(
            diff=_empty_diff("Here are more options from the current selection."),
            show_more=True,
        )

    return None


def _is_color_only_message(lower_text: str, color: str) -> bool:
    """Guard against a color word appearing incidentally inside a longer,
    more complex request that should really go to full LLM extraction
    (e.g. "something like the red one but for a wedding in 3 days").
    """
    word_count = len(lower_text.split())
    return word_count <= 6


def _match_cheaper(last_results: list[Product]) -> FastPathMatch | None:
    if not last_results:
        # Nothing to compare against — ask the LLM to interpret "cheaper"
        # relative to whatever budget context it can infer instead.
        return None

    min_price = min(p.price for p in last_results)
    new_budget = math.floor((min_price * BUDGET_REDUCTION_FACTOR) / PRICE_ROUNDING) * PRICE_ROUNDING
    new_budget = max(new_budget, PRICE_ROUNDING)  # never collapse to 0

    diff = IntentExtractionResult(
        budget_max=new_budget,
        assistant_reply=f"Sure — showing options under Rs. {new_budget:,}.",
    )
    return FastPathMatch(diff=diff)


def _match_style_shift(add: str, remove: str) -> FastPathMatch:
    diff = IntentExtractionResult(
        style_descriptors=[add],
        assistant_reply=f"Got it — leaning more {add}.",
    )
    return FastPathMatch(diff=diff)


def _match_color(color: str) -> FastPathMatch:
    diff = IntentExtractionResult(
        color_preference=color,
        assistant_reply=f"Updated to {color} — here's what matches.",
    )
    return FastPathMatch(diff=diff)


def _match_different_brand(last_results: list[Product]) -> FastPathMatch:
    dominant_brand = _dominant_brand_slug(last_results)
    excluded = [dominant_brand] if dominant_brand else []
    diff = IntentExtractionResult(
        excluded=excluded,
        assistant_reply="Sure — let's look at other brands.",
    )
    return FastPathMatch(diff=diff)


def _dominant_brand_slug(products: list[Product]) -> str | None:
    if not products:
        return None
    counts: dict[str, int] = {}
    for p in products:
        slug = p.id.split(":", 1)[0]
        counts[slug] = counts.get(slug, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]
