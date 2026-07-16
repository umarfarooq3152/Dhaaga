"""Rule-based keyword matching for product occasion and material tagging."""

import logging
from typing import Any

from app.schemas.product import Product
from app.nlp.pakistani_events import infer_product_event
from app.nlp.product_semantics import enrich_product_semantics

logger = logging.getLogger(__name__)

# Define keyword patterns for occasion classification
OCCASION_KEYWORDS = {
    "eid": [
        "eid", "eid ul-fitr", "eid ul-adha", "festive", "celebration",
        "special occasion"
    ],
    "mehndi": ["mehndi", "henna", "pre-wedding", "sangeet"],
    "wedding": [
        "wedding", "bridal", "bride", "groom", "nikah", "walima",
        "shendi", "lehenga"
    ],
    "formal": [
        "formal", "party", "evening", "dinner", "gala", "corporate",
        "professional", "office"
    ],
    "casual": ["casual", "everyday", "daily", "regular", "comfortable", "relaxed"],
}

# Define keyword patterns for material/fabric tags
MATERIAL_KEYWORDS = {
    "cotton": ["cotton", "100% cotton", "pure cotton"],
    "silk": ["silk", "100% silk", "pure silk", "satin"],
    "linen": ["linen", "100% linen", "pure linen"],
    "wool": ["wool", "pure wool", "100% wool"],
    "polyester": ["polyester", "poly"],
    "blend": ["blend", "mixed", "mix", "composition"],
    "embroidered": [
        "embroidered", "embroidery", "embellished", "beadwork",
        "handwork", "hand-embroidered"
    ],
    "printed": ["printed", "print", "digital print", "screen print"],
    "dyed": ["dyed", "tie-dye", "batik"],
}

# Define keyword patterns for style tags
STYLE_KEYWORDS = {
    "traditional": [
        "traditional", "ethnic", "classic", "heritage", "cultural",
        "desi"
    ],
    "modern": ["modern", "contemporary", "minimalist", "sleek"],
    "bohemian": ["bohemian", "boho", "ethnic", "artisan"],
    "vintage": ["vintage", "retro", "classic"],
}


def extract_occasion(product: Product) -> str:
    """Determine primary occasion from product name/description/Shopify tags.

    Merchant-set Shopify tags often name the occasion/collection directly
    (e.g. "Eid Edit 26") more reliably than scanning the scraped
    description's boilerplate copy.
    """
    event = infer_product_event(product)
    if event:
        return event

    text = f"{product.name} {product.category or ''} {product.description} {' '.join(product.shopify_tags)}".lower()

    # Score each occasion
    scores = {}
    for occasion, keywords in OCCASION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[occasion] = score

    # Return highest scoring occasion, default to "casual"
    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "casual"


def extract_tags(product: Product) -> list[str]:
    """Extract material, style, and other relevant tags from product,
    including the merchant's own Shopify tags as a signal."""
    text = f"{product.name} {product.category or ''} {product.description} {' '.join(product.shopify_tags)}".lower()
    tags = []

    # Check material keywords
    for material, keywords in MATERIAL_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(material)

    # Check style keywords
    for style, keywords in STYLE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(style)

    # Add size-related tags
    for size in product.sizes:
        if "xs" in size.lower():
            tags.append("petite")
            break
        elif "3xl" in size.lower() or "4xl" in size.lower():
            tags.append("plus-size")
            break

    # Add color count indicator
    if len(product.colors) > 5:
        tags.append("multi-color")

    return sorted(list(set(tags)))  # Remove duplicates and sort


def tag_product(product: Product) -> Product:
    """Enrich product with occasion and tags based on keyword matching.
    
    Args:
        product: Product with name/description but empty occasion/tags
        
    Returns:
        Product with occasion and tags populated
    """
    try:
        product.occasion = extract_occasion(product)
        product.tags = extract_tags(product)
        enrich_product_semantics(product)
        logger.debug(f"Tagged product {product.id}: occasion={product.occasion}, tags={product.tags}")
        return product
    except Exception as e:
        logger.error(f"Failed to tag product {product.id}: {e}")
        # Return product with defaults if tagging fails
        product.occasion = "casual"
        product.tags = []
        enrich_product_semantics(product)
        return product


def tag_products_batch(products: list[Product]) -> list[Product]:
    """Tag a batch of products.
    
    Args:
        products: List of products to tag
        
    Returns:
        List of tagged products
    """
    tagged = []
    for product in products:
        tagged_product = tag_product(product)
        tagged.append(tagged_product)

    logger.info(f"Tagged {len(tagged)} products")
    return tagged
