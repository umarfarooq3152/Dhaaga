"""Deterministic color/shade extraction shared by web and extension search."""

import re


BASE_COLORS = (
    "black", "white", "grey", "gray", "blue", "red", "green", "yellow",
    "orange", "pink", "purple", "brown", "beige", "gold", "silver",
    "teal", "turquoise", "peach", "rust", "coral", "khaki", "maroon",
    "bronze", "copper", "multicolor",
)

# Retail labels are deliberately grouped into narrow shade bands.  In
# particular, the unmodified base colors remain separate: asking for "basic
# blue" must not silently include navy, powder blue, or other named shades.
SHADE_ALIASES: dict[str, tuple[str, ...]] = {
    "blue": ("true blue", "classic blue"),
    "light blue": (
        "light blue", "ice blue", "powder blue", "baby blue", "sky blue",
        "pastel blue", "dusty blue",
    ),
    "mid blue": (
        "denim blue", "cornflower blue", "azure", "azure blue", "cerulean",
        "cerulean blue", "steel blue",
    ),
    "bright blue": (
        "bright blue", "royal blue", "cobalt", "cobalt blue", "electric blue",
        "sapphire blue",
    ),
    "dark blue": ("dark blue", "navy", "navy blue", "midnight blue", "prussian blue"),
    "green": ("classic green", "true green"),
    "light green": (
        "light green", "mint", "mint green", "pastel green", "pistachio",
        "pistachio green", "sage", "sage green",
    ),
    "bright green": (
        "bright green", "apple green", "lime", "lime green", "grass green",
        "parrot green",
    ),
    "dark green": (
        "dark green", "emerald", "emerald green", "forest green", "bottle green",
        "olive", "olive green", "hunter green", "racing green",
    ),
    "teal": ("aqua", "turquoise", "sea green", "peacock blue", "peacock green"),
    "dark teal": ("dark teal",),
    "pink": ("classic pink", "rose pink", "candy pink", "bubblegum pink"),
    "light pink": (
        "light pink", "baby pink", "blush", "blush pink", "powder pink",
        "pastel pink", "dusty pink",
    ),
    "warm pink": ("salmon pink", "coral pink"),
    "dark pink": ("dark pink", "hot pink", "fuchsia", "magenta", "rani pink"),
    "red": ("classic red", "true red", "tomato red", "cherry red", "scarlet", "ruby red"),
    "light red": ("light red", "coral red", "salmon red"),
    "dark red": ("dark red", "crimson", "brick red", "blood red", "deep red"),
    "maroon": ("deep maroon", "wine", "burgundy", "oxblood"),
    "light purple": (
        "light purple",
        "lavender",
        "lilac",
        "mauve",
        "orchid",
        "periwinkle",
        "periwinkle blue",
    ),
    "purple": ("classic purple", "violet", "amethyst"),
    "dark purple": (
        "dark purple",
        "deep purple",
        "plum",
        "aubergine",
        "eggplant",
        "indigo",
        "indigo blue",
        "iris",
    ),
    "light yellow": ("light yellow", "pastel yellow", "lemon yellow", "butter yellow"),
    "yellow": ("classic yellow", "true yellow"),
    "dark yellow": ("dark yellow", "golden yellow", "mustard", "mustard yellow", "ochre", "amber"),
    "light orange": ("light orange", "apricot"),
    "orange": ("classic orange", "tangerine"),
    "dark orange": ("dark orange", "burnt orange", "terracotta"),
    "light brown": ("light brown", "sand", "tan", "camel", "caramel", "taupe", "nude"),
    "dark brown": (
        "dark brown", "chocolate", "chocolate brown", "coffee", "coffee brown",
        "mocha", "chestnut", "espresso",
    ),
    "off white": ("off white", "off-white", "ivory", "cream", "eggshell", "bone"),
    "light grey": (
        "light grey", "light gray", "silver grey", "silver gray", "ash grey", "ash gray",
        "dove grey", "dove gray",
    ),
    "dark grey": (
        "dark grey", "dark gray", "steel grey", "steel gray", "slate grey", "slate gray",
        "charcoal", "charcoal grey", "charcoal gray", "gunmetal",
    ),
    "black": ("classic black", "true black", "onyx"),
    "dark black": ("jet black", "dark black"),
    "gold": ("golden", "antique gold", "rose gold", "champagne gold"),
    "silver": ("antique silver",),
    "multicolor": ("multi color", "multi-color", "colourful", "colorful"),
}

_BASIC_MODIFIERS = ("basic", "plain", "standard", "true", "regular")
_LIGHT_MODIFIERS = ("light", "pale", "pastel", "soft")
_DARK_MODIFIERS = ("dark", "deep")


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _build_color_lookup() -> dict[str, str]:
    """Build canonical color aliases once instead of once per product.

    A catalog search can compare tens of thousands of color values. Rebuilding
    every normalized alias set inside each comparison made a two-word query
    spend several seconds in color normalization alone.
    """
    lookup: dict[str, str] = {}
    for canonical, aliases in SHADE_ALIASES.items():
        for alias in (canonical, *aliases):
            lookup[_normalized(alias)] = canonical
    for base in BASE_COLORS:
        normalized_base = "grey" if base == "gray" else base
        # Shade aliases have the same precedence as the original implementation
        # (e.g. retail "Turquoise" belongs to the teal family even though it
        # also appears in BASE_COLORS).
        lookup.setdefault(base, normalized_base)
        for modifier in _BASIC_MODIFIERS:
            lookup.setdefault(f"{modifier} {base}", normalized_base)
        for modifier in _LIGHT_MODIFIERS:
            lookup.setdefault(f"{modifier} {base}", f"light {normalized_base}")
        for modifier in _DARK_MODIFIERS:
            lookup.setdefault(f"{modifier} {base}", f"dark {normalized_base}")
    return lookup


_COLOR_LOOKUP = _build_color_lookup()


def canonical_color(value: str) -> str | None:
    """Normalize one color label while preserving shade specificity."""
    text = _normalized(value)
    if not text:
        return None

    return _COLOR_LOOKUP.get(text, text)


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


def extract_color_options(text: str) -> list[str]:
    """Extract explicit alternative colors without conflating outfit pieces.

    Separators such as "brown or red" express alternatives for one search.
    A phrase such as "dark blue jeans with a black shirt" deliberately stays
    a single-color intent, because "with" relates colors to different items.
    """
    segments = re.split(r"\s*(?:\bor\b|/|,)\s*", text, flags=re.IGNORECASE)
    options: list[str] = []
    if len(segments) > 1:
        for segment in segments:
            color = extract_color(segment)
            if color and color not in options:
                options.append(color)
    if len(options) > 1:
        return options
    color = extract_color(text)
    return [color] if color else []


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
