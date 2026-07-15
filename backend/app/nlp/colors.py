"""Deterministic color/shade extraction shared by web and extension search."""

import re


BASE_COLORS = (
    "black", "white", "grey", "gray", "blue", "red", "green", "yellow",
    "orange", "pink", "purple", "brown", "beige", "gold", "silver",
    "teal", "turquoise", "peach", "rust", "coral", "khaki",
)

SHADE_ALIASES: dict[str, tuple[str, ...]] = {
    "light blue": ("light blue", "sky blue", "powder blue", "baby blue", "pastel blue", "dusty blue"),
    "dark blue": ("dark blue", "navy", "navy blue", "midnight blue", "indigo blue"),
    "bright blue": ("bright blue", "royal blue", "cobalt blue", "electric blue"),
    "light green": ("light green", "mint", "mint green", "pastel green", "sage green"),
    "dark green": ("dark green", "emerald", "emerald green", "forest green", "bottle green", "olive green"),
    "light red": ("light red", "coral red", "salmon red"),
    "dark red": ("dark red", "maroon", "burgundy", "wine", "crimson", "deep red"),
    "light pink": ("light pink", "baby pink", "blush", "blush pink", "pastel pink", "dusty pink"),
    "dark pink": ("dark pink", "hot pink", "fuchsia", "magenta"),
    "light purple": ("light purple", "lavender", "lilac", "mauve"),
    "dark purple": ("dark purple", "plum", "aubergine"),
    "light yellow": ("light yellow", "pastel yellow", "lemon yellow"),
    "dark yellow": ("dark yellow", "mustard", "mustard yellow", "ochre"),
    "light brown": ("light brown", "tan", "camel", "caramel"),
    "dark brown": ("dark brown", "chocolate", "coffee brown"),
    "light grey": ("light grey", "light gray", "silver grey", "silver gray"),
    "dark grey": ("dark grey", "dark gray", "charcoal", "charcoal grey", "charcoal gray"),
    "dark black": ("jet black", "dark black"),
    "off white": ("off white", "off-white", "ivory", "cream"),
}

_BASIC_MODIFIERS = ("basic", "plain", "standard", "true", "regular")
_LIGHT_MODIFIERS = ("light", "pale", "pastel", "soft")
_DARK_MODIFIERS = ("dark", "deep")


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def canonical_color(value: str) -> str | None:
    """Normalize one color label while preserving shade specificity."""
    text = _normalized(value)
    if not text:
        return None

    for canonical, aliases in SHADE_ALIASES.items():
        if text == canonical or text in {_normalized(alias) for alias in aliases}:
            return canonical

    for base in BASE_COLORS:
        normalized_base = "grey" if base == "gray" else base
        if text == base or text in {f"{modifier} {base}" for modifier in _BASIC_MODIFIERS}:
            return normalized_base
        if text in {f"{modifier} {base}" for modifier in _LIGHT_MODIFIERS}:
            return f"light {normalized_base}"
        if text in {f"{modifier} {base}" for modifier in _DARK_MODIFIERS}:
            return f"dark {normalized_base}"
    return text


def extract_color(text: str) -> str | None:
    """Extract the most specific color phrase from conversational text."""
    normalized = _normalized(text)
    candidates: list[tuple[int, str]] = []

    for canonical, aliases in SHADE_ALIASES.items():
        for alias in (canonical, *aliases):
            phrase = _normalized(alias)
            if re.search(rf"\b{re.escape(phrase)}\b", normalized):
                candidates.append((len(phrase), canonical))

    modifiers = (*_BASIC_MODIFIERS, *_LIGHT_MODIFIERS, *_DARK_MODIFIERS)
    for base in BASE_COLORS:
        for modifier in modifiers:
            phrase = f"{modifier} {base}"
            if re.search(rf"\b{re.escape(phrase)}\b", normalized):
                candidates.append((len(phrase), canonical_color(phrase) or phrase))
        if re.search(rf"\b{re.escape(base)}\b", normalized):
            candidates.append((len(base), canonical_color(base) or base))

    return max(candidates, default=(0, None))[1]


def colors_match(requested: str, available: str) -> bool:
    """Match exact shade families; base blue does not match dark/light blue."""
    requested_canonical = canonical_color(requested)
    available_canonical = canonical_color(available)
    return bool(requested_canonical and requested_canonical == available_canonical)


def matching_color(requested: str, available_colors: list[str]) -> str | None:
    return next(
        (available for available in available_colors if colors_match(requested, available)),
        None,
    )
