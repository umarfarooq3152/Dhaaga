"""Map Shopify product JSON to normalized Product schema."""

import logging
import re
from typing import Any

from app.schemas.product import Product

logger = logging.getLogger(__name__)


def _contains_word(keyword: str, text: str) -> bool:
    """Whole-word match, tolerant of a simple trailing plural "s" — plain
    substring matching lets single-word keywords like "boy" match inside
    unrelated words (e.g. "boyfriend", a legitimate unisex jeans-fit term),
    but strict `\\bword\\b` matching then misses real plural product
    listings (e.g. keyword "fragrance" not matching category "Fragrances").
    """
    return re.search(rf"\b{re.escape(keyword)}s?\b", text) is not None

# Some brands (e.g. Nishat Linen's "Freedom to Buy" line) list raw fabric
# sold by the meter as regular catalog products, using a per-unit pricing
# scheme that produces nonsensical near-zero prices (e.g. Rs. 9.20) for
# what Shopify's own storefront shows as a much larger real price. These
# aren't finished garments and don't belong in an outfit-discovery catalog
# at all, so they're excluded at ingestion rather than mis-priced.
UNIT_SALE_PRODUCT_TYPES = {"meter", "meters", "yard", "yards"}
MIN_PLAUSIBLE_PRICE = 200.0  # backstop against other brands' similar data quirks

# Many Pakistani fashion brands' Shopify stores also sell non-garment
# merchandise (home textiles, fragrances, jewelry, stationery) in the same
# catalog. A shopper searching "wedding lehenga" getting a pillow cover back
# is a real, observed relevance bug (Gul Ahmed's "Ideas Home" cushion line;
# Maria B perfumes; Sana Safinaz sells a notebook with no category tag at
# all). Checked against both product_type AND title, since several of these
# have no product_type set.
NON_APPAREL_KEYWORDS = [
    "pillow", "cushion", "bed sheet", "bedsheet", "quilt", "blanket", "curtain",
    "rug", "showpiece", "vase", "tray", "coaster", "candle", "home decor",
    "perfume", "fragrance", "cologne", "eau de",
    "bangle", "bracelet", "necklace", "earring", "jewelry", "jewellery", "ring set",
    "notebook", "diary", "journal", "sunglasses", "fashion glasses",
    "wallet", "potli", "mug", "kitchen", "bbq", "eye mask", "sleep mask",
    # Footwear — a real observed case (Outfitters' "Closed Shoes" category)
    # showing up in what should be a clothing-only catalog.
    "shoes", "sneakers", "sandals", "slides", "chappal", "footwear",
    "heels", "flats", "loafers", "boots", "flip flop", "flip-flop",
]

# This app has no kids onboarding/sizing flow at all (Menswear/Womenswear
# only), so kids items have no correct department to slot into. Real
# observed case: Gul Ahmed's "Toddler Boy Multi Sweatshirt" and "Junior
# Boy Clay Printed Sweatshirt" surfaced in a plain adult "sweatshirt"
# search. Beechtree's kids line uses its own category prefix ("BTK-East"
# / "BTK-West") with no kids keyword in the title at all, so it needs a
# separate category-prefix check rather than a title keyword.
KIDS_KEYWORDS = ["kids", "kid", "boys", "girls", "boy", "girl", "toddler", "infant", "newborn"]
KIDS_CATEGORY_PREFIXES = ("btk",)


def _extract_shopify_tags(shopify_product: dict[str, Any]) -> list[str]:
    """Shopify returns `tags` as either a list or a single comma-separated
    string depending on the store/API version — normalize to a list."""
    raw = shopify_product.get("tags") or []
    if isinstance(raw, str):
        return [t.strip() for t in raw.split(",") if t.strip()]
    return [str(t).strip() for t in raw if str(t).strip()]


def _is_non_apparel(title: str, category: str | None, shopify_tags: list[str]) -> bool:
    text = f"{title} {category or ''} {' '.join(shopify_tags)}".lower()
    return any(_contains_word(keyword, text) for keyword in NON_APPAREL_KEYWORDS)


def _is_kids_apparel(
    title: str, category: str | None, shopify_tags: list[str], vendor: str | None = None
) -> bool:
    category_lower = (category or "").lower()
    if category_lower.startswith(KIDS_CATEGORY_PREFIXES) or category_lower == "kids":
        return True

    # Real observed case: Beechtree's "2 PIECE EMBROIDERED SUIT" has no
    # kids keyword in its title or category at all — only its Shopify
    # tags ("Kids", "Little Girls", "child") reveal it's a kids item.
    # `vendor` is another real observed case — Zellbury and Outfitters use
    # it as a per-product department/age label ("ZELLBURY GIRLS", "Boys
    # Junior", "Girls Toddler") independent of the brand-level department.
    text = f"{title} {category_lower} {' '.join(shopify_tags)} {vendor or ''}".lower()
    return any(_contains_word(keyword, text) for keyword in KIDS_KEYWORDS)


def _is_fully_out_of_stock(shopify_product: dict[str, Any]) -> bool:
    """True if every variant is unavailable — nothing purchasable at all.

    Real observed case: a large fraction of the cached catalog (86% of
    one Zellbury sample, 56% of RadStore) was completely sold out but
    still being shown as if in stock, since availability was never
    checked at ingestion.
    """
    variants = shopify_product.get("variants", [])
    if not variants:
        return False
    return all(not variant.get("available", True) for variant in variants)


def extract_colors(shopify_product: dict[str, Any]) -> list[str]:
    """Extract unique colors from Shopify product options, falling back to
    a variant-title heuristic only when no explicit Color option exists.

    The heuristic (first "/"-separated segment = color) assumes a
    Color/Size variant order — it's wrong for products with a different
    option order (e.g. Size/Color/Fabric), so it must never run
    alongside a successful options-based match or it pollutes the set
    with sizes/fabric names instead.
    """
    colors = set()
    for option in shopify_product.get("options", []):
        if option.get("name", "").lower() == "color":
            colors.update(option.get("values", []))

    if not colors:
        for variant in shopify_product.get("variants", []):
            title = variant.get("title", "")
            if "/" in title:
                potential_color = title.split("/")[0].strip()
                if potential_color and len(potential_color) < 30:
                    colors.add(potential_color)

    return sorted(list(colors)) if colors else ["Default"]


def extract_sizes(shopify_product: dict[str, Any]) -> list[str]:
    """Extract unique sizes from Shopify product options, falling back to
    a variant-title heuristic only when no explicit Size option exists
    (see extract_colors — same reasoning, opposite end of the title).

    Matches the option name loosely ("size" appearing anywhere), not just
    the exact strings "Size"/"Sizes" — real observed case: Gul Ahmed names
    its size option "Men Sizes", which the exact-match check used to miss
    entirely, silently falling back to "One Size" for every product.
    """
    sizes = set()
    for option in shopify_product.get("options", []):
        if _contains_word("size", option.get("name", "").lower()):
            sizes.update(option.get("values", []))

    if not sizes:
        for variant in shopify_product.get("variants", []):
            title = variant.get("title", "")
            if "/" in title:
                parts = title.split("/")
                if len(parts) > 1:
                    potential_size = parts[-1].strip()
                    if potential_size and len(potential_size) < 20:
                        sizes.add(potential_size)

    return sorted(list(sizes)) if sizes else ["One Size"]


def extract_images(shopify_product: dict[str, Any]) -> tuple[str, str | None]:
    """Extract primary and secondary product images."""
    images = shopify_product.get("images", [])

    primary = None
    secondary = None

    if images:
        primary = images[0].get("src", "")
        if len(images) > 1:
            secondary = images[1].get("src", "")

    return primary or "", secondary


def map_shopify_to_product(
    shopify_product: dict[str, Any], brand_slug: str, domain: str
) -> Product | None:
    """Convert Shopify product JSON to normalized Product schema.
    
    Args:
        shopify_product: Raw Shopify product dict from /products.json
        brand_slug: Brand slug for product ID (e.g., 'limelight')
        domain: Brand domain for product URL
        
    Returns:
        Product instance or None if required fields missing
    """
    try:
        product_id = str(shopify_product.get("id", ""))
        title = (shopify_product.get("title") or "").strip()
        description = (shopify_product.get("body_html") or "").strip()
        handle = shopify_product.get("handle", "")
        category = (shopify_product.get("product_type") or "").strip() or None
        vendor = (shopify_product.get("vendor") or "").strip() or None
        shopify_tags = _extract_shopify_tags(shopify_product)

        if not product_id or not title:
            logger.warning(
                f"Skipping product: missing id or title in {shopify_product}"
            )
            return None

        if _is_fully_out_of_stock(shopify_product):
            logger.debug(f"Skipping out-of-stock product: {title}")
            return None

        if category and category.lower() in UNIT_SALE_PRODUCT_TYPES:
            logger.debug(f"Skipping unit-sale product (sold by {category}): {title}")
            return None

        if _is_non_apparel(title, category, shopify_tags):
            logger.debug(f"Skipping non-apparel product: {title} ({category})")
            return None

        if _is_kids_apparel(title, category, shopify_tags, vendor):
            logger.debug(f"Skipping kids apparel (no kids flow supported): {title} ({category})")
            return None

        # Extract price from first available variant
        price = 0.0
        for variant in shopify_product.get("variants", []):
            if variant.get("price"):
                try:
                    price = float(variant.get("price", 0))
                    break
                except (ValueError, TypeError):
                    pass

        if price < MIN_PLAUSIBLE_PRICE:
            logger.debug(f"Skipping implausibly-priced product (Rs. {price}): {title}")
            return None

        colors = extract_colors(shopify_product)
        sizes = extract_sizes(shopify_product)
        primary_image, secondary_image = extract_images(shopify_product)

        if not primary_image:
            # A handful of listings (seen on real Zellbury data — hand
            # towels, dupattas) have no image uploaded at all yet. A
            # product card with no image is useless in a visual shopping
            # app, and rendering `<img src="">` also throws a React warning.
            logger.debug(f"Skipping product with no image: {title}")
            return None

        # Build product URL
        product_url = f"https://{domain}/products/{handle}" if handle else ""

        # Create product with composite ID
        return Product(
            id=f"{brand_slug}:{product_id}",
            name=title,
            description=description,
            price=price,
            colors=colors,
            sizes=sizes,
            occasion="",  # Will be filled by keyword_matcher
            category=category,
            tags=[],  # Will be filled by keyword_matcher
            shopify_tags=shopify_tags,
            image=primary_image,
            secondaryImage=secondary_image,
            product_url=product_url,
        )
    except Exception as e:
        logger.error(f"Failed to map Shopify product: {e}", exc_info=True)
        return None


def map_shopify_batch(
    shopify_products: list[dict[str, Any]], brand_slug: str, domain: str
) -> list[Product]:
    """Map a batch of Shopify products to Product schema.
    
    Args:
        shopify_products: List of raw Shopify product dicts
        brand_slug: Brand slug
        domain: Brand domain
        
    Returns:
        List of successfully mapped Product instances
    """
    products = []
    for sp in shopify_products:
        product = map_shopify_to_product(sp, brand_slug, domain)
        if product:
            products.append(product)

    logger.info(f"Mapped {len(products)}/{len(shopify_products)} Shopify products")
    return products
