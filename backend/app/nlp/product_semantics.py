"""Versioned semantic enrichment for catalog products.

This layer canonicalizes merchant metadata once at ingestion/cache load. It is
not a user-language parser: conversational semantics remain the LLM's job.
"""

import re
from functools import lru_cache

from app.nlp.apparel_classification import (
    CASUAL_FABRICS,
    FORMAL_FABRICS,
    HEAVY_WORK_MARKERS,
    LIGHT_WORK_MARKERS,
    classify_product,
    extract_classification_request,
    strip_negated_apparel_evidence,
)
from app.nlp.garments import extract_garment_descriptors, extract_primary_garment
from app.nlp.pakistani_events import infer_product_event
from app.schemas.product import Product, ProductSemantics


SEMANTIC_PROFILE_VERSION = "catalog-semantic-v4"
FESTIVE_EVIDENCE = (
    "party wear", "occasion wear", "festive wear", "wedding wear",
    "bridal wear", "luxury pret", "festive", "fancy", "bridal",
)


@lru_cache(maxsize=512)
def _evidence_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])")


def _present_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    normalized = text.lower()
    return [
        phrase for phrase in phrases
        if _evidence_pattern(phrase).search(normalized)
    ]


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def enrich_product_semantics(product: Product) -> Product:
    """Attach a compact canonical profile, preserving the Product identity."""
    core_source = " ".join((
        product.name,
        product.category or "",
        " ".join(product.shopify_tags),
        " ".join(product.tags),
    ))
    family = (
        extract_primary_garment(product.category or "")
        or extract_primary_garment(product.name)
        or extract_primary_garment(" ".join(product.shopify_tags))
    )
    classification = extract_classification_request(core_source)
    product_classification = classify_product(product)
    # Negative merchant copy (for example "without embellishment") must not
    # become positive work evidence in the retrieval profile.
    full_source = strip_negated_apparel_evidence(
        " ".join((core_source, product.description or ""))
    )
    formal_fabrics = _present_phrases(full_source, FORMAL_FABRICS)
    casual_fabrics = _present_phrases(full_source, CASUAL_FABRICS)
    heavy_work = _present_phrases(full_source, HEAVY_WORK_MARKERS)
    light_work = _present_phrases(full_source, LIGHT_WORK_MARKERS)
    festive_markers = _present_phrases(full_source, FESTIVE_EVIDENCE)
    embellishment = "heavy" if heavy_work else "light" if light_work else "none"
    evidence_sources = []
    evidence_terms = (
        *FORMAL_FABRICS, *CASUAL_FABRICS, *HEAVY_WORK_MARKERS,
        *LIGHT_WORK_MARKERS, *FESTIVE_EVIDENCE,
    )
    for label, source in (
        ("title_or_category", f"{product.name} {product.category or ''}"),
        ("shopify_tags", " ".join(product.shopify_tags)),
        ("description", product.description or ""),
        ("normalized_tags", " ".join(product.tags)),
    ):
        if _present_phrases(source, evidence_terms):
            evidence_sources.append(label)
    attributes = list(dict.fromkeys(filter(None, (
        *product.tags,
        *extract_garment_descriptors(core_source),
        classification.formality,
        classification.tradition,
        "activewear" if product_classification.activewear else None,
        *[color.lower() for color in product.colors if color.lower() != "default"],
    ))))
    audience = [product.department] if product.department else []
    if product.is_kids:
        audience.append("kids")
    # Product occasion is already classified by the ingestion tagger. Only
    # inspect raw metadata for callers that enrich an untagged Product.
    event = product.occasion or infer_product_event(product)
    occasions = [event.lower()] if event else []

    # Put canonical concepts first; descriptions are truncated because long
    # merchant care instructions add noise but little retrieval value.
    semantic_text = _clean(" ".join(filter(None, (
        family,
        " ".join(audience),
        " ".join(occasions),
        " ".join(attributes),
        product.name,
        product.category,
        " ".join(product.shopify_tags),
        (product.description or "")[:600],
    )))).lower()
    product.semantics = ProductSemantics(
        version=SEMANTIC_PROFILE_VERSION,
        product_family=family,
        audiences=list(dict.fromkeys(audience)),
        occasions=list(dict.fromkeys(occasions)),
        attributes=attributes,
        formality=product_classification.formality,
        tradition=product_classification.tradition,
        fabrics=list(dict.fromkeys((*formal_fabrics, *casual_fabrics))),
        embellishment=embellishment,
        festive_markers=festive_markers,
        evidence_sources=evidence_sources,
        search_text=semantic_text,
    )
    return product


def ensure_product_semantics(product: Product) -> Product:
    if (
        not product.semantics
        or product.semantics.version != SEMANTIC_PROFILE_VERSION
        or not product.semantics.search_text
    ):
        return enrich_product_semantics(product)
    return product


def enrich_products_semantics(products: list[Product]) -> list[Product]:
    return [enrich_product_semantics(product) for product in products]
