"""Complete rule-based garment formality and Eastern/Western classification."""

from dataclasses import dataclass
from functools import lru_cache
import re

from app.schemas.product import Product


CASUAL = 0
SEMI_FORMAL = 1
FORMAL = 2
PARTY = 3
BRIDAL = 4


@dataclass(frozen=True)
class ApparelClassification:
    formality: int
    tradition: str | None
    activewear: bool = False


@dataclass(frozen=True)
class ClassificationRequest:
    formality: str | None = None
    tradition: str | None = None
    activewear: bool = False


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


@lru_cache(maxsize=512)
def _phrases_pattern(phrases: tuple[str, ...]) -> re.Pattern[str]:
    alternatives = "|".join(
        re.escape(_normalized(phrase))
        for phrase in sorted(phrases, key=len, reverse=True)
    )
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])")


def _has(text: str, *phrases: str) -> bool:
    return bool(phrases and _phrases_pattern(tuple(phrases)).search(text))


ACTIVEWEAR_MARKERS = (
    "activewear", "sportswear", "athleisure", "gym wear", "gym clothes",
    "workout", "exercise clothes", "training", "dri fit", "moisture wicking",
    "compression", "performance fabric", "performance", "seamless",
    "4 way stretch", "sports bra", "bike shorts", "yoga pants",
    "training tee", "training jacket", "sports hijab", "sports abaya",
    "running shoes", "trainers", "windbreaker",
)

EASTERN_ITEMS = (
    "kurta", "kameez", "shalwar", "salwar", "gharara", "sharara",
    "dupatta", "sherwani", "achkan", "khussa", "angrakha", "pishwas",
    "lehenga", "lawn suit", "chiffon suit", "organza suit", "velvet suit",
    "raw silk suit", "abaya", "saree", "prince coat", "waistcoat",
)
FUSION_ITEMS = (
    "palazzo", "cigarette pants", "kurti", "cape", "peplum", "jumpsuit",
    "tunic", "leggings", "tights", "sandals", "flats",
)
WESTERN_ITEMS = (
    "button down", "dress shirt", "office shirt", "oxford shirt", "shirt",
    "t shirt", "tee", "polo", "blouse", "tank top", "camisole", "crop top",
    "jeans", "trousers", "dress pants", "dress", "gown", "blazer", "skirt",
    "shorts", "sneakers", "heels", "loafers", "cardigan", "shrug",
)

HARD_CASUAL_ITEMS = (
    "t shirt", "tee", "jeans", "denim jeans", "shorts", "sneakers",
    "leggings", "tights", "denim jacket",
)
HARD_DRESSY_ITEMS = (
    "sherwani", "gharara", "sharara", "bridal gown", "bridal lehenga",
)
BRIDAL_MARKERS = (
    "bridal", "bride", "couture", "groom", "dabka", "kora", "zardozi",
)
HEAVY_WORK_MARKERS = (
    "heavily embellished", "heavy embroidery", "sequins", "sequin", "sequined",
    "mirror work", "gota", "gotta", "handwork", "hand work", "beadwork",
    "bead work", "mukaish", "mukesh", "kamdani", "crystal work", "pearl work",
    "zari", "dabka", "kora", "tilla", "jeweled", "jewelled", "beaded",
    "statement work", "stone work",
)
LIGHT_WORK_MARKERS = (
    "light embroidery", "embroidered", "embroidery", "embellished",
    "embellishment", "digital print",
)
FORMAL_FABRICS = (
    "chiffon", "silk", "satin", "organza", "velvet", "net", "raw silk",
)
CASUAL_FABRICS = (
    "jersey", "knit", "knitted", "lawn", "cotton", "denim", "flannel", "ribbed",
)
FORMAL_CONSTRUCTION = (
    "button down", "button front", "dress shirt", "office shirt", "oxford shirt",
    "structured", "tailored", "collared", "collar", "cuffs", "fitted",
    "woven", "crisp",
)
CASUAL_CONSTRUCTION = (
    "graphic", "drawstring", "elastic waist", "pull over", "pullover", "loose",
)


_WORK_TERM_PATTERN = (
    r"(?:embellished|embellishment|embroidered|embroidery|sequins?|sequined|"
    r"mirror work|gota|gotta|hand ?work|bead ?work|mukaish|mukesh|kamdani|"
    r"crystal work|pearl work|zari|dabka|kora|tilla|beaded|stone work)"
)
_NEGATED_WORK_PATTERN = re.compile(
    rf"\b(?:no|without)\s+(?:any\s+)?(?:(?:heavy|light)\s+)?"
    rf"{_WORK_TERM_PATTERN}(?:\s+(?:or|and)\s+"
    rf"(?:(?:heavy|light)\s+)?{_WORK_TERM_PATTERN})*\b",
)


def strip_negated_apparel_evidence(value: str) -> str:
    """Remove explicitly absent work so it cannot become positive evidence."""
    return _NEGATED_WORK_PATTERN.sub(" ", _normalized(value))


def _tradition(text: str) -> str | None:
    if _has(text, *EASTERN_ITEMS):
        return "eastern"
    if _has(text, *FUSION_ITEMS):
        return "fusion"
    if _has(text, *WESTERN_ITEMS):
        return "western"
    return None


def _base_tier(text: str) -> int:
    """Item-only baseline before fabric and construction adjustments."""
    if _has(text, *BRIDAL_MARKERS):
        return BRIDAL
    if _has(text, "sherwani", "gharara", "sharara", "cocktail dress"):
        return PARTY
    if _has(
        text, "angrakha", "peplum top", "gown", "blazer", "waistcoat",
        "achkan", "lehenga", "pishwas",
    ):
        return FORMAL
    if _has(text, "dress pants", "suiting trousers", "formal dress shoes"):
        return FORMAL
    if _has(text, "wrap dress", "shirt dress", "polo", "blouse", "trousers"):
        return SEMI_FORMAL
    if _has(text, "palazzo", "cigarette pants", "khussa", "heels", "loafers"):
        return SEMI_FORMAL
    if _has(text, "unstitched lawn 3 piece", "lawn 3 piece", "3 piece lawn"):
        return SEMI_FORMAL
    if _has(text, "stitched lawn suit", "3 piece", "three piece"):
        return SEMI_FORMAL
    if _has(text, "kurta", "kurti", "kameez", "shalwar", "salwar"):
        return CASUAL
    if _has(text, "unstitched lawn 2 piece", "lawn 2 piece", "2 piece lawn"):
        return CASUAL
    if _has(text, "tank top", "camisole", "crop top", "cardigan", "shrug"):
        return CASUAL
    if _has(text, "maxi", "slip dress", "day dress", "dress", "shirt"):
        return CASUAL
    if _has(
        text,
        "leggings", "tights", "sandals", "flats", "denim jacket",
        "joggers", "track pants",
    ):
        return CASUAL
    return SEMI_FORMAL


def classify_apparel_text(value: str) -> ApparelClassification:
    """Classify item + fabric + construction using every guide-level rule."""
    text = strip_negated_apparel_evidence(value)
    tradition = _tradition(text)
    swimwear = _has(text, "swimwear", "swimsuit", "bathing suit")
    performance_item = _has(
        text,
        "leggings", "tights", "track pants", "joggers", "tank top",
        "camisole", "t shirt", "tee", "jacket",
    )
    performance_detail = _has(text, "stretch", "high waist")
    activewear = not swimwear and (
        _has(text, *ACTIVEWEAR_MARKERS)
        or (performance_item and performance_detail)
    )

    # Activewear is a separate taxonomy. A training tee is activewear, while a
    # plain cotton tee merely worn to the gym remains casual.
    if activewear:
        return ApparelClassification(CASUAL, tradition, activewear=True)

    # Item-level exclusions outrank premium fabric and marketing language.
    casual_button_down = _has(text, "button down", "button front") and _has(
        text, "flannel", "denim", "casual print"
    )
    knit_cardigan = _has(text, "cardigan") and _has(text, "knit", "knitted")
    if _has(text, *HARD_CASUAL_ITEMS) or casual_button_down or knit_cardigan:
        return ApparelClassification(CASUAL, tradition or "western")

    tier = _base_tier(text)
    hard_dressy = _has(text, *HARD_DRESSY_ITEMS)
    casual_fabric = _has(text, *CASUAL_FABRICS)
    formal_fabric = _has(text, *FORMAL_FABRICS)
    light_work = _has(text, *LIGHT_WORK_MARKERS)
    heavy_work = _has(text, *HEAVY_WORK_MARKERS)
    formal_construction = _has(text, *FORMAL_CONSTRUCTION)
    casual_construction = _has(text, *CASUAL_CONSTRUCTION)

    # Fabric modifies only items whose formality genuinely depends on fabric.
    fabric_sensitive = _has(
        text,
        "shirt", "polo", "blouse", "kurta", "kurti", "kameez", "suit",
        "dress", "maxi", "slip", "palazzo", "shalwar", "salwar", "shrug", "tunic",
        "khussa", "heels",
    )
    if fabric_sensitive and casual_fabric and not formal_construction:
        tier = max(CASUAL, tier - 1)
    if formal_fabric:
        tier = max(tier, FORMAL)

    # Construction and embellishment refine the fabric-derived tier.
    if casual_construction and not formal_fabric:
        tier = max(CASUAL, tier - 1)
    if formal_construction:
        tier = max(tier, FORMAL)
    if light_work and tier < FORMAL:
        tier += 1
    if heavy_work:
        tier = max(tier, PARTY)

    # Item-specific guide refinements.
    if _has(text, "angrakha"):
        tier = max(tier, FORMAL)
    if _has(text, "button down", "button front") and _has(
        text, "flannel", "denim", "casual print"
    ):
        tier = CASUAL
    if _has(text, "unstitched lawn 3 piece", "lawn 3 piece", "3 piece lawn"):
        tier = max(tier, SEMI_FORMAL)
    if _has(text, "khaddar"):
        tier = max(tier, SEMI_FORMAL)
    if _has(text, "cape") and (_has(text, "event wear") or light_work or heavy_work):
        tier = max(tier, FORMAL if not heavy_work else PARTY)
    if _has(text, "maxi") and (formal_construction or light_work):
        tier = max(tier, FORMAL)
    if _has(text, "slip dress") and _has(text, "satin", "silk"):
        tier = max(tier, PARTY)
    if _has(text, "crop top") and heavy_work:
        tier = PARTY
    if _has(text, "velvet", "net"):
        tier = max(tier, FORMAL)
    if hard_dressy:
        tier = max(tier, PARTY)

    # Explicit merchant tags apply last, while hard item exclusions above have
    # already returned and cannot be incorrectly upgraded.
    if _has(text, "bridal wear"):
        tier = BRIDAL
    elif _has(text, "party wear", "occasion wear"):
        tier = max(tier, PARTY)
    elif _has(text, "formal", "formal wear"):
        tier = max(tier, FORMAL)
    elif _has(text, "casual", "daily wear", "everyday") and not (
        hard_dressy or heavy_work or formal_fabric
    ):
        tier = min(tier, SEMI_FORMAL)

    return ApparelClassification(tier, tradition, activewear=False)


def classify_product(product: Product) -> ApparelClassification:
    return classify_apparel_text(
        " ".join(
            (
                product.name,
                product.category or "",
                product.description or "",
                " ".join(product.shopify_tags),
                " ".join(product.tags),
            )
        )
    )


@lru_cache(maxsize=512)
def extract_classification_request(value: str) -> ClassificationRequest:
    text = _normalized(value)
    activewear = classify_apparel_text(text).activewear
    if activewear:
        formality = None
    elif _has(text, "semi formal", "semiformal", "daily formal"):
        formality = "semi-formal"
    elif _has(text, "bridal"):
        formality = "bridal"
    elif _has(text, "party", "party wear", "occasion wear"):
        formality = "party"
    elif _has(text, "formal", "formal wear"):
        formality = "formal"
    elif _has(text, "casual", "casual wear", "daily wear", "everyday"):
        formality = "casual"
    else:
        formality = None

    if _has(text, "eastern", "eastern wear", "desi", "ethnic"):
        tradition = "eastern"
    elif _has(text, "western", "western wear"):
        tradition = "western"
    elif _has(text, "fusion", "fusion wear"):
        tradition = "fusion"
    else:
        tradition = None
    return ClassificationRequest(formality, tradition, activewear)


def matches_classification(value: Product | str, request_text: str | None) -> bool:
    if not request_text or not request_text.strip():
        return True
    request = extract_classification_request(request_text or "")
    if not (request.formality or request.tradition or request.activewear):
        return True
    if (
        isinstance(value, Product)
        and value.semantics is not None
        and value.semantics.version == "catalog-semantic-v4"
    ):
        # Catalog semantic profiles already contain evidence-based tradition
        # and formality. Re-parsing long descriptions for every broad western/
        # eastern result is both redundant and noticeably slower.
        classification = ApparelClassification(
            value.semantics.formality,
            value.semantics.tradition,
            activewear="activewear" in value.semantics.attributes,
        )
    else:
        classification = (
            classify_product(value) if isinstance(value, Product) else classify_apparel_text(value)
        )
    if request.activewear and not classification.activewear:
        return False
    if request.tradition and classification.tradition != request.tradition:
        return False
    if request.formality == "casual" and (
        classification.activewear or classification.formality > SEMI_FORMAL
    ):
        return False
    if request.formality == "semi-formal" and not (
        SEMI_FORMAL <= classification.formality <= FORMAL
    ):
        return False
    if request.formality == "formal" and classification.formality < FORMAL:
        return False
    if request.formality == "party" and classification.formality < PARTY:
        return False
    if request.formality == "bridal" and classification.formality < BRIDAL:
        return False
    return True
