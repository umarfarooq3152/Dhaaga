"""Deterministic, pure fast-path classifier for common chat refinements.

Runs BEFORE the query-intent cache or any LLM call, so the most common
follow-up turns ("cheaper", "show more", ...) never pay LLM latency/cost.
Returns None when nothing matches, so the caller falls through to the
cache/LLM path.
"""

import math
import re
from dataclasses import dataclass

from app.schemas.product import Product
from app.schemas.session import IntentExtractionResult, SessionState
from app.kids_age import extract_child_age_months
from app.nlp.colors import extract_color


CHEAPER_PHRASES = ["cheaper", "less expensive", "lower budget", "more affordable", "budget option"]
MORE_FORMAL_PHRASES = ["more formal", "dressier", "fancier"]
MORE_CASUAL_PHRASES = ["more casual", "less formal", "simpler"]
DIFFERENT_BRAND_PHRASES = ["different brand", "another brand", "other brands"]
SHOW_MORE_PHRASES = ["show more", "more options", "more results", "see more"]
UNSURE_PHRASES = {"unsure", "not sure", "i'm not sure", "i am not sure", "either", "you decide"}

BUDGET_REDUCTION_FACTOR = 0.9
PRICE_ROUNDING = 1000

# Detects a shopper buying for a child, so session_service can set
# wants_kids=True deterministically (see is_kids_request) rather than
# relying on an LLM prompt instruction — the LLM (especially the Groq
# fallback) was observed not reliably following a "shopping for a kid"
# instruction, extracting a nonsensical size="kids" and surfacing adult
# womenswear as if it matched a toddler's outfit.
KIDS_KEYWORDS = [
    "toddler", "infant", "newborn", "baby girl", "baby boy",
    "kids outfit", "kids clothes", "kid's", "kids'",
    "children's wear", "childrens wear", "children's clothing",
]
KIDS_AGE_PATTERN = re.compile(r"\b(\d{1,2})\s*[- ]?years?\b")
KIDS_MAX_AGE = 12
# Words confirming an age number refers to a child, not e.g. "2 years
# experience" or "married 2 years" — required alongside the age pattern
# when the text doesn't literally say "old" (real observed case: "2 year
# ld daughter", a typo/transcription artifact dropping the "o" from "old",
# didn't match a strict "...years old" pattern at all).
KIDS_RELATION_WORDS = ["daughter", "son", "kid", "child", "baby", "toddler"]


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

    department = extract_department(lower)
    if department and _is_department_only_message(lower):
        label = "women's" if department == "women" else "men's"
        return FastPathMatch(
            diff=IntentExtractionResult(
                department=department,
                assistant_reply=f"Got it — I'll keep these results to {label} clothing.",
            )
        )

    if lower.rstrip(".!?") in UNSURE_PHRASES and current.occasion:
        return FastPathMatch(
            diff=IntentExtractionResult(
                assistant_reply=(
                    "That's completely fine. Would you prefer something understated, "
                    "dressy, or heavily festive?"
                ),
                clarify=True,
            )
        )

    if any(phrase in lower for phrase in CHEAPER_PHRASES):
        return _match_cheaper(last_results)

    if any(phrase in lower for phrase in MORE_FORMAL_PHRASES):
        return _match_style_shift(add="formal", remove="casual")

    if any(phrase in lower for phrase in MORE_CASUAL_PHRASES):
        return _match_style_shift(add="casual", remove="formal")

    color_match = extract_color(lower)
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


def extract_department(lower_text: str) -> str | None:
    """Extract an explicitly stated apparel audience from a refinement."""
    if re.search(r"\b(women|woman|women's|womens|ladies|female)\b", lower_text):
        return "women"
    if re.search(r"\b(men|man|men's|mens|male)\b", lower_text):
        return "men"
    return None


def _is_department_only_message(lower_text: str) -> bool:
    normalized = re.sub(r"[^a-z']+", " ", lower_text).strip()
    return normalized in {
        "women", "woman", "women's", "womens", "ladies", "female",
        "men", "man", "men's", "mens", "male",
        "for women", "for men", "women's clothing", "womens clothing",
        "men's clothing", "mens clothing", "i need women's clothing",
        "i need men's clothing", "show women", "show men",
    }


def _is_color_only_message(lower_text: str, color: str) -> bool:
    """Guard against a color word appearing incidentally inside a longer,
    more complex request that should really go to full LLM extraction
    (e.g. "something like the red one but for a wedding in 3 days").
    """
    word_count = len(lower_text.split())
    compound_terms = {
        "wedding", "mehndi", "eid", "formal", "casual", "party",
        "lehenga", "kurta", "shalwar", "kameez", "sherwani", "shirt",
        "dress", "suit", "women", "woman", "women's", "men", "man", "men's",
    }
    words = set(re.findall(r"[a-z']+", lower_text))
    return word_count <= 6 and not (words - {color}) & compound_terms


def is_kids_request(text: str) -> bool:
    """True if the message indicates the shopper is buying for a child —
    used by session_service to set wants_kids=True on the merged session
    state regardless of which path (fast-path or LLM) handled the rest of
    the message's extraction, so occasion/color/style are still picked up
    normally alongside the kids signal."""
    lower_text = text.lower().strip()

    if extract_child_age_months(text) is not None:
        return True

    if any(keyword in lower_text for keyword in KIDS_KEYWORDS):
        return True

    match = KIDS_AGE_PATTERN.search(lower_text)
    if match is None or int(match.group(1)) > KIDS_MAX_AGE:
        return False

    # A small age number alone isn't enough signal ("2 years experience",
    # "married 2 years") — require "old" or an explicit relation word to
    # confirm it's actually describing a child's age.
    return "old" in lower_text or any(word in lower_text for word in KIDS_RELATION_WORDS)


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
