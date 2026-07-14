"""Map Shopify product JSON to normalized Product schema."""

import logging
from typing import Any

from app.schemas.product import Product

logger = logging.getLogger(__name__)


def extract_colors(shopify_product: dict[str, Any]) -> list[str]:
    """Extract unique colors from Shopify product options and variants."""
    colors = set()

    # Check for Color option in options array
    for option in shopify_product.get("options", []):
        if option.get("name", "").lower() == "color":
            colors.update(option.get("values", []))

    # Also extract from variant titles (e.g., "Red / Small")
    for variant in shopify_product.get("variants", []):
        title = variant.get("title", "")
        # Simple heuristic: first part before '/' is usually color
        if "/" in title:
            potential_color = title.split("/")[0].strip()
            if potential_color and len(potential_color) < 30:
                colors.add(potential_color)

    return sorted(list(colors)) if colors else ["Default"]


def extract_sizes(shopify_product: dict[str, Any]) -> list[str]:
    """Extract unique sizes from Shopify product options and variants."""
    sizes = set()

    # Check for Size option in options array
    for option in shopify_product.get("options", []):
        if option.get("name", "").lower() in ("size", "sizes"):
            sizes.update(option.get("values", []))

    # Also extract from variant titles (e.g., "Red / Small")
    for variant in shopify_product.get("variants", []):
        title = variant.get("title", "")
        # Simple heuristic: last part after '/' is usually size
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
        title = shopify_product.get("title", "").strip()
        description = shopify_product.get("body_html", "").strip()
        handle = shopify_product.get("handle", "")

        if not product_id or not title:
            logger.warning(
                f"Skipping product: missing id or title in {shopify_product}"
            )
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

        colors = extract_colors(shopify_product)
        sizes = extract_sizes(shopify_product)
        primary_image, secondary_image = extract_images(shopify_product)

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
            tags=[],  # Will be filled by keyword_matcher
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
