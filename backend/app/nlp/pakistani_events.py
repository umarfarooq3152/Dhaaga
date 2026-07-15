"""Pakistani occasion vocabulary and deterministic apparel expectations."""

from dataclasses import dataclass
import re

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
                 ("lehenga", "gharara", "sharara", "angrakha", "pishwas", "frock", "kurta", "waistcoat", "shalwar kameez", "3 piece", "3-piece"),
                 ("yellow", "mustard", "green", "orange", "pink", "lime", "multicolor", "multi"),
                 ("embroidered", "embroidery", "mirror work", "gotta", "gota", "sequins", "embellished", "festive", "traditional")),
    EventProfile("nikah", ("nikah", "nikkah", "nikkah ceremony"),
                 ("pishwas", "lehenga", "gharara", "sharara", "angrakha", "kurta", "waistcoat", "shalwar kameez", "3 piece", "3-piece"),
                 ("white", "ivory", "cream", "beige", "pastel", "blush", "silver"),
                 ("embroidered", "embroidery", "embellished", "formal", "festive", "traditional")),
    EventProfile("baraat", ("baraat", "barat", "shaadi", "shadi", "wedding", "bridal"),
                 ("lehenga", "gharara", "sharara", "pishwas", "sherwani", "prince coat", "waistcoat", "3 piece", "3-piece"),
                 ("red", "maroon", "burgundy", "gold", "crimson"),
                 ("bridal", "embroidered", "embellished", "zari", "formal", "festive", "traditional")),
    EventProfile("walima", ("walima", "valima", "reception"),
                 ("gown", "maxi", "pishwas", "lehenga", "sharara", "prince coat", "suit", "3 piece", "3-piece"),
                 ("pastel", "silver", "grey", "blue", "mint", "lavender", "peach", "ivory"),
                 ("embroidered", "embellished", "formal", "luxury", "festive")),
    EventProfile("engagement", ("engagement", "mangni", "baat pakki", "ring ceremony"),
                 ("maxi", "gown", "pishwas", "sharara", "kurta", "waistcoat", "suit", "3 piece", "3-piece"),
                 ("pastel", "pink", "blue", "mint", "lavender", "peach"),
                 ("embroidered", "embellished", "formal", "festive")),
    EventProfile("eid", ("eid", "eid ul fitr", "eid-ul-fitr", "eid ul adha", "eid-ul-adha", "bakra eid", "choti eid"),
                 ("kurta", "shalwar kameez", "gharara", "sharara", "pishwas", "waistcoat", "sherwani", "3 piece", "3-piece", "2 piece", "2-piece"),
                 (), ("embroidered", "embellished", "festive", "traditional", "printed")),
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
                 ("dress", "maxi", "gown", "pishwas", "sharara", "suit"),
                 ("white", "pink", "pastel", "lavender", "peach"), ("party", "embroidered", "formal", "festive")),
    EventProfile("baby shower", ("baby shower", "godh bharai"),
                 ("dress", "maxi", "gown", "kurta", "shalwar kameez", "suit"),
                 ("pastel", "pink", "blue", "mint", "yellow"), ("comfortable", "embroidered", "formal", "festive")),
    EventProfile("iftar", ("iftar", "iftari", "ramadan dinner", "sehri", "ramzan dinner"),
                 ("abaya", "kurta", "shalwar kameez", "kaftan", "waistcoat", "3 piece", "3-piece"),
                 (), ("modest", "embroidered", "traditional", "formal")),
    EventProfile("birthday", ("birthday", "salgreh"),
                 ("dress", "frock", "maxi", "shirt", "kurta", "suit"), (), ("party", "formal", "printed")),
    EventProfile("graduation", ("graduation", "convocation"),
                 ("suit", "dress", "kurta", "shalwar kameez", "shirt", "blazer"),
                 ("black", "navy", "white", "beige"), ("formal", "minimal", "classic")),
    EventProfile("jummah", ("jummah", "juma", "friday prayer"),
                 ("kurta", "shalwar kameez", "waistcoat"),
                 ("white", "cream", "blue", "grey"), ("traditional", "plain", "embroidered")),
    EventProfile("basant", ("basant", "kite festival"),
                 ("kurta", "shalwar kameez", "frock", "3 piece", "3-piece"),
                 ("yellow", "mustard", "orange", "green"), ("printed", "embroidered", "festive")),
    EventProfile("independence day", ("independence day", "14 august", "fourteenth august", "azadi day"),
                 ("kurta", "shalwar kameez", "shirt", "waistcoat"),
                 ("green", "white"), ("printed", "traditional")),
    EventProfile("pakistan day", ("pakistan day", "23 march", "twenty third march"),
                 ("kurta", "shalwar kameez", "shirt", "waistcoat"),
                 ("green", "white"), ("printed", "traditional")),
    EventProfile("cultural day", ("cultural day", "culture day", "heritage day", "sindhi culture day", "school function"),
                 ("kurta", "shalwar kameez", "ajrak", "waistcoat", "frock", "gharara"),
                 (), ("traditional", "ethnic", "embroidered", "printed")),
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
    EventProfile("office", ("office", "workwear", "job interview", "interview"),
                 ("suit", "shirt", "trouser", "kurta", "shalwar kameez", "blazer"),
                 ("black", "navy", "white", "beige", "grey"), ("formal", "minimal", "plain")),
    EventProfile("casual", ("casual", "daily wear", "everyday", "university", "college"),
                 ("shirt", "t shirt", "t-shirt", "kurta", "trouser", "jeans", "2 piece", "2-piece"),
                 (), ("casual", "printed", "plain", "comfortable")),
)

_BY_NAME = {event.name: event for event in EVENTS}


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase.lower())}(?![a-z0-9])", text) is not None


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


def event_match_score(product: Product, event_name: str) -> float:
    """Score whether a garment is culturally appropriate for an event."""
    canonical = extract_event(event_name) or event_name.lower()
    event = _BY_NAME.get(canonical)
    if event is None:
        return 1.0 if product.occasion == event_name.lower() else 0.0

    text = " ".join((
        product.name, product.category or "", product.description or "",
        " ".join(product.shopify_tags), " ".join(product.tags), " ".join(product.colors),
    )).lower()
    if product.occasion == event.name or any(_contains_phrase(text, alias) for alias in event.aliases):
        return 1.0

    garment = any(_contains_phrase(text, term) for term in event.garments)
    color = any(_contains_phrase(text, term) for term in event.colors)
    festive = any(_contains_phrase(text, term) for term in event.festive_markers)
    if not garment or not (color or festive):
        return 0.0
    return 0.5 + (0.25 if color else 0.0) + (0.25 if festive else 0.0)


def infer_product_event(product: Product) -> str | None:
    """Infer the most explicit Pakistani event named in product metadata."""
    text = " ".join((product.name, product.category or "", product.description or "", " ".join(product.shopify_tags)))
    return extract_event(text)
