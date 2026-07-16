"""Deterministic garment/style extraction for conversational web search."""

import re
from difflib import SequenceMatcher

from app.nlp.colors import extract_color


_DESCRIPTOR_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("shalwar kameez", (r"\bshalwar\s+kameez(?:es)?\b", r"\bsalwar\s+kameez(?:es)?\b")),
    ("shirt dress", (r"\bshirt\s+dress(?:es)?\b",)),
    ("wrap dress", (r"\bwrap\s+dress(?:es)?\b",)),
    ("cocktail dress", (r"\bcocktail\s+dress(?:es)?\b",)),
    ("slip dress", (r"\bslip\s+dress(?:es)?\b",)),
    ("cigarette pants", (r"\bcigarette\s+pants?\b",)),
    ("peplum top", (r"\bpeplum(?:\s+tops?)?\b",)),
    ("crop top", (r"\bcrop\s+tops?\b",)),
    ("polo", (r"\bpolo\s+shirts?\b", r"\bpolos?\b")),
    ("t-shirt", (r"\bt[ -]?shirts?\b", r"\btees?\b")),
    ("tank top", (r"\btank\s+tops?\b", r"\bcamisoles?\b")),
    ("sweatshirt", (r"\bsweatshirts?\b",)),
    ("tracksuit", (r"\btrack\s*suits?\b",)),
    ("co-ord", (r"\bco[ -]?ords?(?:\s+sets?)?\b", r"\bmatching\s+sets?\b")),
    ("prince coat", (r"\bprince\s+coats?\b",)),
    ("waistcoat", (r"\bwaist\s*coats?\b",)),
    ("vest", (r"\bvests?\b", r"\bkoti\b",)),
    ("blouse", (r"\bblouses?\b",)),
    ("tunic", (r"\btunics?\b",)),
    ("kurti", (r"\bkurtis?\b",)),
    ("kurta", (r"\bkurtas?\b",)),
    ("kameez", (r"\bkameez(?:es)?\b",)),
    ("lehenga", (r"\blehengas?\b",)),
    ("sherwani", (r"\bsherwanis?\b",)),
    ("achkan", (r"\bachkans?\b",)),
    ("gharara", (r"\bghararas?\b",)),
    ("sharara", (r"\bshararas?\b",)),
    ("shalwar", (r"\b(?:shalwar|salwar)s?\b",)),
    ("pishwas", (r"\bpishwas\b",)),
    ("saree", (r"\bsar(?:ee|i)s?\b",)),
    ("abaya", (r"\babayas?\b",)),
    ("maxi", (r"\bmaxis?\b",)),
    ("gown", (r"\bgowns?\b",)),
    ("suit", (r"\b(?:2|3|two|three)[ -]?piece(?:\s+\w+){0,2}\s+suits?\b", r"\bsuits?\b")),
    ("dress", (r"\bdress(?:es)?\b",)),
    ("shirt", (r"\bshirts?\b",)),
    ("top", (r"\btops?\b",)),
    ("palazzo", (r"\bpalazzos?\b",)),
    ("leggings", (r"\bleggings?\b", r"\btights?\b")),
    ("joggers", (r"\bjoggers?\b", r"\btrack\s+pants?\b")),
    ("jeans", (r"\bjeans?\b", r"\bdenims?\b")),
    ("shorts", (r"\bshorts\b", r"\bbike\s+short\b")),
    ("skirt", (r"\bskirts?\b",)),
    ("trousers", (r"\btrousers?\b", r"\bpants?\b")),
    ("blazer", (r"\bblazers?\b",)),
    ("shrug", (r"\bshrugs?\b",)),
    ("cape", (r"\bcapes?\b",)),
    ("cardigan", (r"\bcardigans?\b",)),
    ("jacket", (r"\bjackets?\b",)),
    ("coat", (r"\bcoats?\b",)),
    ("windbreaker", (r"\bwindbreakers?\b",)),
    ("hoodie", (r"\bhoodies?\b",)),
    ("sweater", (r"\bsweaters?\b",)),
    ("jumpsuit", (r"\bjumpsuits?\b",)),
    ("sports bra", (r"\bsports?\s+bras?\b",)),
    ("underwear", (r"\b(?:underwear|briefs?|boxers?|lingerie)\b",)),
    ("socks", (r"\bsocks?\b",)),
    ("scarf", (r"\bscar(?:f|ves)\b",)),
    ("headwear", (r"\b(?:headwear|caps?|hats?|beanies?)\b",)),
    ("bag", (r"\b(?:bags?|handbags?|totes?|clutches?|cross[ -]?body)\b",)),
    ("belt", (r"\bbelts?\b",)),
    ("dupatta", (r"\bdupattas?\b",)),
    ("shawl", (r"\bshawls?\b",)),
    ("swimwear", (r"\b(?:swimwear|swimsuits?|bathing suits?)\b",)),
    ("shoes", (
        r"\bdress\s+shoes?\b",
        r"\b(?:shoes?|footwear|sneakers?|sandals?|slides?|loafers?|heels?|"
        r"flats?|khussas?|trainers?|boots?)\b",
    )),
    ("knitted", (r"\bknit(?:ted|wear)?\b",)),
    ("embroidered", (r"\bembroider(?:ed|y)\b",)),
    ("printed", (r"\b(?:printed|print)\b",)),
    ("striped", (r"\bstrip(?:e|ed|es|ing)\b",)),
    ("leather", (r"\b(?:faux|pu|genuine)?\s*leather\b",)),
    ("denim", (r"\bdenim\b",)),
    ("suede", (r"\bsuede\b",)),
    ("cotton", (r"\bcotton\b",)),
    ("linen", (r"\blinen\b",)),
    ("silk", (r"\bsilk\b",)),
    ("wool", (r"\bwool(?:len)?\b",)),
    ("velvet", (r"\bvelvet\b",)),
    ("chiffon", (r"\bchiffon\b",)),
    ("organza", (r"\borganza\b",)),
    ("satin", (r"\bsatin\b",)),
    ("khaddar", (r"\bkhaddar\b",)),
    ("lawn", (r"\blawn\b",)),
    ("oversized", (r"\bover[ -]?sized\b",)),
    ("slim fit", (r"\bslim[ -]?fits?\b",)),
    ("regular fit", (r"\bregular[ -]?fits?\b",)),
    ("relaxed fit", (r"\brelaxed[ -]?fits?\b",)),
    ("baggy", (r"\bbaggy\b",)),
    ("wide leg", (r"\bwide[ -]?legs?\b",)),
    ("straight fit", (r"\bstraight[ -]?(?:fit|leg)s?\b",)),
    ("cropped", (r"\bcropped\b",)),
    ("formal", (r"\bformal(?:wear| wear)?\b",)),
    ("casual", (r"\bcasual(?:wear| wear)?\b",)),
    ("semi-formal", (r"\bsemi[ -]?formal\b",)),
    ("party", (r"\bparty\s+wear\b",)),
    ("activewear", (r"\b(?:activewear|sportswear|gym wear|workout clothes)\b",)),
    ("eastern", (r"\beastern(?: wear)?\b",)),
    ("western", (r"\bwestern(?: wear)?\b",)),
)

# These labels materially constrain search and must never be accepted merely
# because an LLM inferred them. They are retained only when the shopper used a
# corresponding phrase in this turn (or when already persisted from an earlier
# explicitly grounded turn).
_STRICT_STYLE_LABELS = {
    "formal",
    "casual",
    "semi formal",
    "semi-formal",
    "party",
    "festive",
    "traditional",
}

_STYLE_DESCRIPTORS = {
    "knitted",
    "embroidered",
    "formal",
    "casual",
    "semi-formal",
    "party",
    "activewear",
    "eastern",
    "western",
    "printed", "leather", "denim", "suede", "cotton", "linen", "silk",
    "wool", "velvet", "chiffon", "organza", "satin", "khaddar", "lawn",
    "oversized", "slim fit", "regular fit", "relaxed fit", "baggy",
    "wide leg", "straight fit", "cropped",
    "striped",
}

# Merchant product types often use a store-specific family label instead of
# the shopper's everyday garment word. These aliases supplement the explicit
# vocabulary above; the title/category still has to name the same product
# family, so a description mentioning "polo-style" cannot turn a camisole
# into a polo result.
_GARMENT_METADATA_ALIASES: dict[str, tuple[str, ...]] = {
    "activewear": (
        "performance", "training", "dri fit", "moisture wicking",
        "sports bra", "sports hijab", "sports abaya", "bike short",
        "yoga pant", "track pant", "running shoe",
    ),
    "shoes": ("footwear", "oxford", "derby", "pump", "chappal"),
    "sweater": ("knitwear", "pullover", "jumper"),
    "sweatshirt": ("sweat shirt",),
    "jacket": ("outerwear", "bomber", "puffer"),
    "trousers": ("bottoms", "pants"),
    "top": ("fashion top", "eastern top", "western top"),
    "co-ord": ("coord", "coord set", "co ord set"),
    "tracksuit": ("track suit", "track set"),
    "suit": ("2 piece", "3 piece", "two piece", "three piece"),
    "shalwar kameez": ("eastern suit",),
}

_GARMENT_TYPO_ALIASES = {
    "tshirt": "t-shirt",
    "polo": "polo",
    "shirt": "shirt",
    "blouse": "blouse",
    "sweater": "sweater",
    "hoodie": "hoodie",
    "jacket": "jacket",
    "sweatshirt": "sweatshirt",
    "tracksuit": "tracksuit",
    "top": "top",
    "coat": "coat",
    "vest": "vest",
    "jean": "jeans",
    "trouser": "trousers",
    "kurta": "kurta",
    "kurti": "kurti",
    "kameez": "kameez",
    "shalwar": "shalwar",
    "lehenga": "lehenga",
    "gharara": "gharara",
    "sharara": "sharara",
    "sherwani": "sherwani",
    "dress": "dress",
    "skirt": "skirt",
    "belt": "belt",
}

_STYLE_CANONICAL_ALIASES = {
    "stripe": "striped",
    "stripes": "striped",
    "striped": "striped",
}


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def extract_search_descriptors(text: str) -> list[str]:
    """Return explicitly named garments/styles, avoiding nested categories."""
    matches: list[tuple[int, int, str]] = []
    lowered = text.lower()
    # "Dress up like a bandit" uses dress as a verb; treating it as the
    # Western dress category blocks the intended daaku/kurta fallback.
    lowered = re.sub(r"\bdress(?:ed)?\s+up\b", " ", lowered)
    for descriptor, patterns in _DESCRIPTOR_PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if match:
                matches.append((match.start(), match.end(), descriptor))
                break

    # Prefer the longest phrase when patterns overlap: "polo shirt" is a polo,
    # not both a polo and a generic shirt.
    accepted: list[tuple[int, int, str]] = []
    for start, end, descriptor in sorted(matches, key=lambda item: item[1] - item[0], reverse=True):
        if any(start < used_end and end > used_start for used_start, used_end, _ in accepted):
            continue
        accepted.append((start, end, descriptor))
    return [item[2] for item in sorted(accepted)]


def extract_garment_descriptors(text: str) -> list[str]:
    """Return concrete product categories, excluding style/family labels."""
    return [
        descriptor
        for descriptor in extract_search_descriptors(text)
        if descriptor not in _STYLE_DESCRIPTORS
    ]


def extract_primary_garment(text: str) -> str | None:
    """Return the first explicitly requested product in conversational order."""
    garments = extract_garment_descriptors(text)
    if garments:
        return garments[0]

    best: tuple[float, int, str] | None = None
    typo_text = re.sub(r"\bdress(?:ed)?\s+up\b", " ", text.lower())
    for index, token in enumerate(re.findall(r"[a-z]+", typo_text)):
        if len(token) < 4 or extract_color(token):
            continue
        singular = token[:-1] if token.endswith("s") else token
        for alias, garment in _GARMENT_TYPO_ALIASES.items():
            ratio = SequenceMatcher(None, singular, alias).ratio()
            if ratio >= 0.75 and (best is None or ratio > best[0]):
                best = (ratio, index, garment)
    return best[2] if best else None


def without_garment_descriptors(descriptors: list[str]) -> list[str]:
    """Keep subjective refinements while removing product/audience fields."""
    result: list[str] = []
    for descriptor in descriptors:
        cleaned = _normalized(descriptor)
        while garments := extract_garment_descriptors(cleaned):
            previous = cleaned
            for garment in garments:
                cleaned = re.sub(
                    rf"\b{re.escape(_normalized(garment))}\b", " ", cleaned
                )
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned == previous:
                cleaned = ""
                break
        if cleaned in {"2 piece", "3 piece", "two piece", "three piece"}:
            cleaned = ""
        # Audience belongs in SessionState.department, never in strict style
        # keywords. A provider returning style="female" caused women's Mehndi
        # searches to require the literal word "female" on every product.
        cleaned = re.sub(
            r"\b(?:women(?: s)?|womens?|woman(?: s)?|ladies|female|"
            r"men(?: s)?|mens?|man(?: s)?|gents|male|girls?|boys?)\b",
            " ",
            cleaned,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = _STYLE_CANONICAL_ALIASES.get(cleaned, cleaned)
        if cleaned and cleaned not in {item.lower() for item in result}:
            result.append(cleaned)
    return result


def matches_garment_text(value: str, garment: str | None) -> bool:
    """Match a product title/type/tag string to one canonical garment family."""
    if not garment:
        return True
    canonical = _normalized(garment)
    normalized = _normalized(value)
    aliases = (canonical, *_GARMENT_METADATA_ALIASES.get(canonical, ()))
    return any(
        re.search(rf"\b{re.escape(_normalized(alias))}s?\b", normalized)
        for alias in aliases
    )


def ground_style_descriptors(text: str, provider_descriptors: list[str]) -> list[str]:
    """Remove inferred hard styles and add explicit deterministic descriptors."""
    explicit = extract_search_descriptors(text)
    explicit_keys = {item.lower() for item in explicit}
    grounded = []
    for item in provider_descriptors:
        key = item.lower().strip()
        inferred_garments = extract_garment_descriptors(item)
        if key in _STRICT_STYLE_LABELS and key not in explicit_keys:
            continue
        if inferred_garments and not any(
            garment.lower() in explicit_keys for garment in inferred_garments
        ):
            continue
        grounded.append(item)
    for item in explicit:
        if item.lower() not in {existing.lower().strip() for existing in grounded}:
            grounded.append(item)
    return grounded
