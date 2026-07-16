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
from app.nlp.garments import (
    extract_primary_garment,
    extract_search_descriptors,
    without_garment_descriptors,
)
from app.nlp.pakistani_events import extract_event
from app.nlp.apparel_classification import extract_classification_request


CHEAPER_PHRASES = ["cheaper", "less expensive", "lower budget", "more affordable", "budget option"]
MORE_FORMAL_PHRASES = ["more formal", "dressier", "fancier"]
MORE_CASUAL_PHRASES = ["more casual", "less formal", "simpler"]
DIFFERENT_BRAND_PHRASES = ["different brand", "another brand", "other brands"]
SHOW_MORE_PHRASES = ["show more", "more options", "more results", "see more"]
UNSURE_PHRASES = {"unsure", "not sure", "i'm not sure", "i am not sure", "either", "you decide"}
GREETING_PATTERN = re.compile(
    r"^(?:hey|hi|hello|hiya|(?:hey|hi|hello)[, ]+how are you|"
    r"salam|assalam(?:[ -]?o[ -]?alaikum)?|"
    r"how are you|how(?:'s| is) it going|what(?:'s| is) up)[!.? ]*$",
    re.IGNORECASE,
)

NEGATIVE_STYLE_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("embellished", (
        "embellished", "embellishment", "embroidered", "embroidery",
        "sequins", "sequin", "mirror work", "zari", "beadwork",
    )),
    ("heavy embellishment", ("heavy", "heavy work", "flashy", "too fancy")),
    ("silk", ("silk",)),
    ("chiffon", ("chiffon",)),
    ("organza", ("organza",)),
    ("velvet", ("velvet",)),
    ("lawn", ("lawn",)),
    ("printed", ("printed", "print")),
)


def extract_excluded_styles(text: str) -> list[str]:
    """Canonical negative evidence from explicit without/no/not wording."""
    lower = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    if not re.search(r"\b(?:without|no|not|avoid|exclude)\b", lower):
        return []
    result = []
    for canonical, aliases in NEGATIVE_STYLE_ALIASES:
        if any(re.search(rf"\b{re.escape(alias)}\b", lower) for alias in aliases):
            result.append(canonical)
    return result

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
    "junior clothes", "junior cloths", "junior clothing", "junior wear",
    "juniors clothes", "juniors cloths", "juniors clothing", "juniors wear",
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


def is_control_message(text: str) -> bool:
    """True only for UI/session controls that do not require fashion semantics.

    Product, occasion, vibe, typo, and free-form shopping interpretation belongs
    to the LLM-first path. Deterministic handling remains for cheap state actions
    such as greeting, show-more, removal, and explicit audience-only switches.
    """
    lower = text.lower().strip()
    return bool(
        GREETING_PATTERN.fullmatch(lower)
        or lower.rstrip(".!?") in UNSURE_PHRASES
        or _is_department_only_message(lower)
        or any(phrase in lower for phrase in CHEAPER_PHRASES)
        or any(phrase in lower for phrase in MORE_FORMAL_PHRASES)
        or any(phrase in lower for phrase in MORE_CASUAL_PHRASES)
        or any(phrase in lower for phrase in DIFFERENT_BRAND_PHRASES)
        or any(phrase in lower for phrase in SHOW_MORE_PHRASES)
        or _clear_filter_field(lower) is not None
        or re.search(r"\b(?:without|remove)\s+[a-z][a-z -]*\b", lower)
    )


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

    if GREETING_PATTERN.fullmatch(lower):
        return FastPathMatch(
            diff=IntentExtractionResult(
                assistant_reply=(
                    "I'm doing well — thanks for asking! Tell me what you're shopping for, "
                    "or start with a product, color, occasion, size, or budget."
                ),
                clarify=True,
            )
        )

    clear_field = _clear_filter_field(lower)
    if clear_field:
        return FastPathMatch(
            diff=IntentExtractionResult(
                clear_fields=[clear_field],
                assistant_reply=f"Removed the {clear_field} filter and refreshed your results.",
            )
        )

    if re.search(r"\b(?:remove|ignore|drop|without|no|not|avoid|exclude|any)\b", lower):
        removed_styles = without_garment_descriptors(extract_search_descriptors(lower))
        removal_match = re.search(
            r"\b(?:remove|ignore|drop|without|no|not|avoid|exclude)\s+(?:the\s+)?(.+)$",
            lower,
        )
        if removal_match:
            requested = re.sub(r"[^a-z0-9]+", " ", removal_match.group(1)).strip()
            for current_style in current.style_descriptors:
                normalized_style = re.sub(r"[^a-z0-9]+", " ", current_style.lower()).strip()
                if normalized_style and (
                    normalized_style == requested
                    or normalized_style in requested
                    or requested in normalized_style
                ):
                    removed_styles.append(current_style)
        removed_styles = list(dict.fromkeys(removed_styles))
        excluded_styles = extract_excluded_styles(lower)
        if "embellished" in excluded_styles:
            removed_styles = list(dict.fromkeys([
                *removed_styles, "embroidered", "embellished",
            ]))
        if removed_styles or excluded_styles:
            return FastPathMatch(
                diff=IntentExtractionResult(
                    remove_styles=removed_styles,
                    excluded_styles=excluded_styles,
                    assistant_reply=(
                        f"Removed {' and '.join(removed_styles or excluded_styles)} and refreshed your results."
                    ),
                )
            )

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

    classification = extract_classification_request(lower)
    if classification.activewear and extract_primary_garment(lower) is None:
        return FastPathMatch(
            diff=IntentExtractionResult(
                style_descriptors=["activewear"],
                semantic_query="activewear performance training clothing",
                soft_preferences=["style_descriptors"],
                assistant_reply="Showing activewear and performance clothing for your workout.",
            )
        )

    color_match = extract_color(lower)
    category_match = extract_primary_garment(lower)
    explicit_styles = without_garment_descriptors(extract_search_descriptors(lower))
    occasion = extract_event(lower)
    budget = extract_budget_max(lower)
    size = extract_size(lower)
    if (category_match or explicit_styles or occasion) and _is_simple_structured_search(
        lower,
        color_match,
        category_match,
        explicit_styles,
        occasion,
    ):
        return FastPathMatch(
            diff=IntentExtractionResult(
                category=category_match,
                color_preference=color_match,
                style_descriptors=explicit_styles,
                department=department,
                occasion=occasion,
                budget_max=budget,
                size=size,
                assistant_reply=(
                    f"Showing exact {category_match} options that match your request."
                ),
            )
        )
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


def _clear_filter_field(lower_text: str) -> str | None:
    normalized = re.sub(r"[^a-z]+", " ", lower_text).strip()
    aliases = {
        "occasion": ("occasion", "event"),
        "style": ("style", "fit", "material", "fabric"),
        "category": ("category", "product type", "garment"),
        "color": ("color", "colour"),
        "budget": ("budget", "price"),
        "size": ("size",),
        "age": ("age",),
    }
    if not re.search(r"\b(?:remove|clear|ignore|drop|without|any|all)\b", normalized):
        return None
    for field, words in aliases.items():
        if any(re.search(rf"\b{re.escape(word)}\b", normalized) for word in words):
            return field
    return None


def _is_simple_structured_search(
    lower_text: str,
    color: str | None,
    category: str | None,
    styles: list[str],
    occasion: str | None,
) -> bool:
    """Recognize plain structured searches without paying LLM latency.

    Keep this deliberately narrow: unknown descriptive words ("silk", "baggy",
    "earthy") force the full extraction path so they are never discarded.
    """
    normalized = re.sub(r"[^a-z0-9]+", " ", lower_text).strip()
    phrases = [*([category] if category else []), *(styles or []), *([color] if color else []), *([occasion] if occasion else [])]
    for phrase in phrases:
        normalized_phrase = re.sub(r"[^a-z0-9]+", " ", phrase.lower()).strip()
        phrase_pattern = (
            r"strip(?:e|ed|es|ing)" if normalized_phrase == "striped"
            else rf"{re.escape(normalized_phrase)}s?"
        )
        normalized = re.sub(rf"\b{phrase_pattern}\b", " ", normalized)
    normalized = re.sub(
        r"\b(?:under|below|upto|up to|less than|max(?:imum)?|budget(?: of)?|within)\s*"
        r"(?:rs\.?|pkr)?\s*\d+(?:\.\d+)?\s*(?:k|thousand|lakh)?\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"\b(?:size|in)\s*(?:xxs|xs|s|m|l|xl|xxl|2xl|3xl|4xl|small|medium|large)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"\b(?:xxs|xs|xxl|2xl|3xl|4xl)\b", " ", normalized)
    normalized = re.sub(
        r"\b\d{1,2}\s*(?:years?|yrs?|months?|mos?)\s*(?:old)?\b|"
        r"\b(?:kids?|children|child|boys?|girls?|son|daughter|toddler|baby)\b",
        " ",
        normalized,
    )
    normalized = re.sub(
        r"\b(?:show|find|need|want|me|i|a|an|some|please|for|the|in|colored|coloured|"
        r"basic|plain|classic|true|men|mens|man|women|womens|woman|male|female|ladies|"
        r"wear|clothing|options|products|sets?|events?|occasion|looking|look|my|old)\b",
        " ",
        normalized,
    )
    return not re.sub(r"\s+", "", normalized)


def extract_budget_max(text: str) -> int | None:
    match = re.search(
        r"\b(?:under|below|upto|up\s+to|less\s+than|max(?:imum)?|budget(?:\s+of)?|within)\s*"
        r"(?:rs\.?|pkr)?\s*(\d+(?:\.\d+)?)\s*(k|thousand|lakh)?\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    multiplier = 100_000 if suffix == "lakh" else 1_000 if suffix in {"k", "thousand"} else 1
    return int(value * multiplier)


def extract_size(text: str) -> str | None:
    match = re.search(
        r"\b(?:size|in)\s*(xxs|xs|s|m|l|xl|xxl|2xl|3xl|4xl|small|medium|large)\b|"
        r"\b(xxs|xs|xxl|2xl|3xl|4xl)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    raw = (match.group(1) or match.group(2)).lower()
    return {"small": "S", "medium": "M", "large": "L", "2xl": "XXL"}.get(raw, raw.upper())


def extract_department(lower_text: str) -> str | None:
    """Extract an explicitly stated apparel audience from a refinement."""
    if re.search(
        r"\b(women|woman|women's|womens|ladies|female|girlfriend|wife)\b|"
        r"\b(?:daughter|baby girl|toddler girl|little girl)\b|"
        r"\b(?:for\s+)?(?:a|my)\s+girl\b",
        lower_text,
    ):
        return "women"
    if re.search(
        r"\b(men|man|men's|mens|male|boyfriend|husband)\b|"
        r"\b(?:son|baby boy|toddler boy|little boy)\b|"
        r"\b(?:for\s+)?(?:a|my)\s+(?:boy|guy)\b",
        lower_text,
    ):
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
    if extract_primary_garment(lower_text) or extract_event(lower_text):
        return False
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

    # Explicit family/child nouns are sufficient even without an age. This
    # prevents "for my son/daughter" from retaining the adult shopping mode.
    if any(
        re.search(rf"\b{re.escape(word)}s?\b", lower_text)
        for word in KIDS_RELATION_WORDS
    ):
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
