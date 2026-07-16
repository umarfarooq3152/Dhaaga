"""Pakistani occasion vocabulary and deterministic apparel expectations."""

from dataclasses import dataclass
import re
from functools import lru_cache

from app.schemas.product import Product


@dataclass(frozen=True)
class EventProfile:
    name: str
    aliases: tuple[str, ...]
    garments: tuple[str, ...]
    colors: tuple[str, ...] = ()
    festive_markers: tuple[str, ...] = ()


EVENTS: tuple[EventProfile, ...] = (
    EventProfile("mehndi", ("mehndi", "mayun", "ubtan", "dholki", "sangeet"),
                 ("lehenga", "choli", "gharara", "sharara", "angrakha", "palazzo", "pishwas", "frock", "short kurta", "kurta", "waistcoat", "shalwar kameez", "3 piece", "3-piece"),
                 ("yellow", "mustard", "green", "orange", "pink", "lime", "multicolor", "multi"),
                 ("embroidered", "embroidery", "mirror work", "gotta", "gota", "sequins", "embellished", "festive", "traditional")),
    EventProfile("nikah", ("nikah", "nikkah", "nikkah ceremony"),
                 ("pishwas", "lehenga", "gharara", "sharara", "angrakha", "kurta", "waistcoat", "shalwar kameez", "3 piece", "3-piece"),
                 ("white", "ivory", "cream", "beige", "pastel", "blush", "silver"),
                 ("embroidered", "embroidery", "embellished", "formal", "festive", "traditional")),
    EventProfile("baraat", ("baraat", "barat", "shaadi", "shadi", "wedding", "bridal", "rukhsati", "winter wedding"),
                 ("lehenga", "choli", "gharara", "sharara", "pishwas", "dress", "sherwani", "prince coat", "waistcoat", "3 piece", "3-piece"),
                 ("red", "maroon", "burgundy", "gold", "crimson"),
                 ("bridal", "embroidered", "embellished", "zari", "formal", "festive", "traditional")),
    EventProfile("walima", ("walima", "valima", "reception"),
                 ("gown", "maxi", "pishwas", "lehenga", "sharara", "prince coat", "suit", "3 piece", "3-piece"),
                 ("pastel", "champagne", "blush", "powder blue", "silver", "grey", "blue", "mint", "lavender", "peach", "ivory"),
                 ("embroidered", "embellished", "formal", "luxury", "festive")),
    EventProfile("engagement", ("engagement", "mangni", "baat pakki", "ring ceremony"),
                 ("lehenga", "choli", "gharara", "maxi", "gown", "pishwas", "sharara", "kurta", "waistcoat", "shalwar kameez", "suit", "3 piece", "3-piece"),
                 ("pastel", "gold", "light pink", "pink", "blue", "mint", "lavender", "peach", "red"),
                 ("embroidered", "embellished", "formal", "festive")),
    EventProfile("eid", ("eid", "eid ul fitr", "eid-ul-fitr", "eid ul adha", "eid-ul-adha", "bakra eid", "choti eid"),
                 ("kurta", "shalwar kameez", "gharara", "sharara", "pishwas", "dress", "waistcoat", "sherwani", "3 piece", "3-piece", "2 piece", "2-piece"),
                 (), ("embroidered", "embellished", "festive", "traditional", "printed")),
    EventProfile("eid milan", ("eid milan", "eid get together", "eid party"),
                 ("kurta", "shalwar kameez", "frock", "gharara", "sharara", "waistcoat", "2 piece", "2-piece", "3 piece", "3-piece"),
                 (), ("party", "festive", "formal", "embroidered", "embellished")),
    EventProfile("chand raat", ("chand raat", "chaand raat"),
                 ("kurta", "shalwar kameez", "frock", "shirt", "trouser", "2 piece", "2-piece"),
                 (), ("casual", "semi formal", "comfortable", "printed", "embroidered")),
    EventProfile("qawwali", ("qawwali", "sufi night", "qawali night"),
                 ("kurta", "shalwar kameez", "angrakha", "waistcoat", "shawl"),
                 ("black", "white", "maroon", "green"),
                 ("embroidered", "traditional", "ethnic")),
    EventProfile("milad", ("milad", "milad un nabi", "eid milad un nabi", "mehfil e milad", "naat khwani"),
                 ("abaya", "kurta", "shalwar kameez", "dupatta", "waistcoat"),
                 ("white", "green", "pastel"), ("modest", "traditional", "embroidered")),
    EventProfile("aqiqah", ("aqiqah", "aqeeqah", "newborn celebration"),
                 ("kurta", "shalwar kameez", "frock", "maxi", "waistcoat"),
                 ("pastel", "white", "blue", "pink"), ("embroidered", "formal", "traditional")),
    EventProfile("bridal shower", ("bridal shower", "bride to be"),
                 ("dress", "jumpsuit", "short kurta", "kurta", "maxi", "gown", "pishwas", "sharara", "suit"),
                 ("white", "pink", "pastel", "lavender", "peach"), ("party", "embroidered", "formal", "festive")),
    EventProfile("baby shower", ("baby shower", "godh bharai"),
                 ("dress", "maxi", "gown", "kurta", "shalwar kameez", "suit"),
                 ("pastel", "pink", "blue", "mint", "yellow"), ("comfortable", "embroidered", "formal", "festive")),
    EventProfile("iftar", ("iftar", "iftari", "ramadan dinner", "sehri", "ramzan dinner"),
                 ("abaya", "kurta", "shalwar kameez", "kaftan", "waistcoat", "3 piece", "3-piece"),
                 (), ("modest", "embroidered", "traditional", "formal")),
    EventProfile("birthday", ("birthday", "salgreh"),
                 ("dress", "frock", "maxi", "shirt", "kurta", "suit"), (), ("party", "formal", "printed")),
    EventProfile("dawat", ("dawat", "daawat", "dinner invite", "family dinner", "post wedding dinner", "walima milan"),
                 ("kurta", "shalwar kameez", "dress", "maxi", "suit", "2 piece", "2-piece", "3 piece", "3-piece"),
                 (), ("semi formal", "formal", "party", "embroidered")),
    EventProfile("farewell", ("farewell", "annual dinner", "university dinner", "college dinner"),
                 ("shalwar kameez", "dress", "gown", "maxi", "suit", "blazer", "kurta"),
                 (), ("formal", "party", "semi formal", "embroidered")),
    EventProfile("graduation", ("graduation", "convocation"),
                 ("suit", "dress", "kurta", "shalwar kameez", "shirt", "blazer"),
                 ("black", "navy", "white", "beige"), ("formal", "minimal", "classic")),
    EventProfile("orientation", ("orientation", "freshers orientation", "university orientation"),
                 ("shalwar kameez", "kurta", "shirt", "trouser", "blazer", "suit"),
                 (), ("formal", "semi formal", "minimal", "classic")),
    EventProfile("color day", ("color day", "colour day", "university color day", "school color day"),
                 ("kurta", "shirt", "dress", "shalwar kameez", "trouser"),
                 (), ("casual", "semi formal", "solid", "plain")),
    EventProfile("sports day", ("sports day", "annual sports", "school annual day"),
                 ("track suit", "tracksuit", "t shirt", "t-shirt", "shirt", "trouser", "kurta"),
                 (), ("casual", "comfortable", "activewear")),
    EventProfile("school function", ("school function", "parent teacher meeting", "parents teacher meeting", "school assembly"),
                 ("kurta", "shalwar kameez", "shirt", "trouser", "2 piece", "2-piece"),
                 (), ("casual", "semi formal", "plain", "minimal")),
    EventProfile("jummah", ("jummah", "juma", "friday prayer"),
                 ("kurta", "shalwar kameez", "waistcoat"),
                 ("white", "cream", "blue", "grey"), ("traditional", "plain", "embroidered")),
    EventProfile("basant", ("basant", "kite festival"),
                 ("kurta", "shalwar kameez", "frock", "3 piece", "3-piece"),
                 ("yellow", "mustard", "orange", "green"), ("printed", "embroidered", "festive")),
    EventProfile("independence day", ("independence day", "14 august", "fourteenth august", "azadi day"),
                 ("kurta", "shalwar kameez", "shirt", "t shirt", "t-shirt", "top", "dress", "skirt", "trouser", "jeans", "co-ord", "waistcoat"),
                 ("green", "white"), ("printed", "traditional")),
    EventProfile("pakistan day", ("pakistan day", "23 march", "twenty third march"),
                 ("kurta", "shalwar kameez", "shirt", "t shirt", "t-shirt", "top", "dress", "skirt", "trouser", "jeans", "co-ord", "waistcoat"),
                 ("green", "white"), ("printed", "traditional")),
    EventProfile("cultural day", ("cultural day", "culture day", "heritage day", "sindhi culture day"),
                 ("kurta", "shalwar kameez", "ajrak", "topi", "phulkari", "peshgabi", "balochi dress", "waistcoat", "frock", "gharara"),
                 (), ("cultural wear", "traditional", "ethnic", "embroidered", "printed")),
    EventProfile("diwali", ("diwali", "deepavali"),
                 ("lehenga", "sari", "saree", "gharara", "sharara", "kurta", "waistcoat"),
                 ("red", "orange", "pink", "gold", "yellow"), ("embroidered", "embellished", "festive", "traditional")),
    EventProfile("holi", ("holi", "festival of colors", "festival of colours"),
                 ("kurta", "shalwar kameez", "shirt", "frock"),
                 ("white", "multicolor", "multi"), ("casual", "traditional", "printed")),
    EventProfile("christmas", ("christmas", "xmas", "christmas dinner"),
                 ("dress", "gown", "suit", "shirt", "blazer", "maxi"),
                 ("red", "green", "white", "gold", "black"), ("party", "formal", "festive")),
    EventProfile("mourning", ("janaza", "funeral", "soyem", "chehlum", "condolence"),
                 ("shalwar kameez", "kurta", "abaya", "dupatta"),
                 ("white", "black", "grey", "navy"), ("plain", "modest", "traditional")),
    EventProfile("office", ("office", "work", "workwear", "presentation", "business presentation", "job interview", "interview", "corporate event", "formal dinner"),
                 ("suit", "shirt", "trouser", "kurta", "shalwar kameez", "blazer"),
                 ("black", "navy", "white", "beige", "grey"), ("formal", "minimal", "plain")),
    EventProfile("casual", ("casual", "daily wear", "everyday", "university", "college"),
                 ("shirt", "t shirt", "t-shirt", "kurta", "trouser", "jeans", "2 piece", "2-piece"),
                 (), ("casual", "printed", "plain", "comfortable")),
)

# Primary and secondary tags used by Pakistani e-commerce catalogs when they
# do not expose a literal event filter. Values are normalized lowercase so
# they match titles, product types, and Shopify tags consistently.
EVENT_FORMALITY_TAGS: dict[str, tuple[str, ...]] = {
    "mehndi": ("party wear", "festive wear", "occasion wear", "party", "festive"),
    "nikah": ("formal", "occasion wear"),
    "baraat": ("bridal wear", "occasion wear", "wedding wear", "formal", "bridal"),
    "walima": ("formal", "occasion wear", "luxury pret"),
    "engagement": ("formal", "occasion wear", "party wear"),
    "eid": ("festive wear", "formal", "eid collection"),
    "eid milan": ("party wear", "festive wear", "formal"),
    "chand raat": ("casual", "semi formal"),
    "bridal shower": ("party wear", "semi formal"),
    "baby shower": ("party wear", "semi formal"),
    "iftar": ("formal", "semi formal", "festive wear"),
    "aqiqah": ("formal", "semi formal"),
    "birthday": ("party wear", "casual"),
    "dawat": ("semi formal", "formal"),
    "farewell": ("formal", "party wear"),
    "graduation": ("formal",),
    "orientation": ("formal", "semi formal"),
    "color day": ("casual", "semi formal"),
    "sports day": ("casual", "activewear"),
    "school function": ("casual", "semi formal"),
    "basant": ("festive wear", "casual"),
    "independence day": ("festive wear", "cultural wear"),
    "pakistan day": ("festive wear", "cultural wear"),
    "cultural day": ("festive wear", "cultural wear"),
    "mourning": ("casual", "modest"),
    "office": ("semi formal", "formal"),
    "casual": ("casual", "daily wear"),
}

_BY_NAME = {event.name: event for event in EVENTS}

# These are broad wearing contexts, not mutually exclusive celebrations. A
# catalog can legitimately label a formal kurta as "casual" while its title,
# colour and construction still make it suitable for a nikah. They therefore
# must not trigger the cross-event contradiction rule below.
_NON_EXCLUSIVE_CONTEXTS = {"casual", "office"}


@lru_cache(maxsize=512)
def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(phrase.lower())}(?![a-z0-9])")


def _contains_phrase(text: str, phrase: str) -> bool:
    return _phrase_pattern(phrase).search(text) is not None


@lru_cache(maxsize=256)
def _phrases_pattern(phrases: tuple[str, ...]) -> re.Pattern[str] | None:
    if not phrases:
        return None
    alternatives = "|".join(
        re.escape(phrase.lower()) for phrase in sorted(phrases, key=len, reverse=True)
    )
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])")


def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    pattern = _phrases_pattern(phrases)
    return pattern is not None and pattern.search(text) is not None


def extract_event(text: str) -> str | None:
    """Return the canonical event for a query/alias, preferring long aliases."""
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    matches: list[tuple[int, str]] = []
    for event in EVENTS:
        for alias in event.aliases:
            normalized_alias = re.sub(r"[^a-z0-9]+", " ", alias.lower()).strip()
            if re.search(rf"\b{re.escape(normalized_alias)}\b", normalized):
                matches.append((len(normalized_alias), event.name))
    return max(matches, default=(0, None))[1]


def is_known_event(name: str | None) -> bool:
    return bool(name and name.lower() in _BY_NAME)


def event_garments(name: str | None) -> tuple[str, ...]:
    """Return the curated garment vocabulary for a canonical event."""
    if not name:
        return ()
    canonical = extract_event(name) or name.lower()
    event = _BY_NAME.get(canonical)
    return event.garments if event else ()


def event_match_score(product: Product, event_name: str) -> float:
    """Score whether a garment is culturally appropriate for an event."""
    normalized_event = event_name.lower()
    canonical = (
        normalized_event
        if normalized_event in _BY_NAME
        else extract_event(event_name) or normalized_event
    )
    event = _BY_NAME.get(canonical)
    if event is None:
        return 1.0 if product.occasion == event_name.lower() else 0.0

    raw_product_event = (product.occasion or "").lower()
    product_event = (
        raw_product_event
        if raw_product_event in _BY_NAME
        else extract_event(raw_product_event)
    )
    if (
        product_event
        and product_event != event.name
        and product_event not in _NON_EXCLUSIVE_CONTEXTS
    ):
        # A product explicitly assigned to another named celebration is a
        # contradiction, not a weak match based on a shared color or garment.
        return 0.0

    text = " ".join((
        product.name, product.category or "", product.description or "",
        " ".join(product.shopify_tags), " ".join(product.tags), " ".join(product.colors),
    )).lower()
    garment = _contains_any_phrase(text, event.garments)
    # Naming an event is not proof that an item is wearable. Henna stencils,
    # décor, favors, and other event merchandise often carry "Mehndi" or
    # "Wedding" tags. Every occasion result must first prove it belongs to a
    # culturally appropriate garment family.
    if not garment:
        return 0.0

    if product.occasion == event.name or _contains_any_phrase(text, event.aliases):
        return 1.0

    color = _contains_any_phrase(text, event.colors)
    formality = EVENT_FORMALITY_TAGS.get(event.name, ())
    festive = _contains_any_phrase(text, (*event.festive_markers, *formality))
    if not (color or festive):
        return 0.0
    if event.name in {"independence day", "pakistan day"}:
        # National-day intent is primarily visual. Green/white clothing leads;
        # printed/traditional festive pieces remain useful near-matches.
        return min(1.0, (0.85 if color else 0.0) + (0.15 if festive else 0.0))
    return 0.5 + (0.25 if color else 0.0) + (0.25 if festive else 0.0)


def infer_product_event(product: Product) -> str | None:
    """Infer the most explicit Pakistani event named in product metadata."""
    text = " ".join((product.name, product.category or "", product.description or "", " ".join(product.shopify_tags)))
    return extract_event(text)
