from app.nlp.product_semantics import (
    SEMANTIC_PROFILE_VERSION,
    enrich_product_semantics,
)
from app.schemas.product import Product


def _product(**updates) -> Product:
    values = {
        "id": "brand:1",
        "name": "Embroidered Lawn Kurta",
        "description": "A bright festive yellow kurta with mirror work.",
        "price": 5000,
        "colors": ["Yellow"],
        "category": "Kurta",
        "occasion": "mehndi",
        "tags": ["embroidered", "traditional"],
        "department": "women",
        "image": "https://example.com/a.jpg",
        "product_url": "https://example.com/a",
    }
    values.update(updates)
    return Product(**values)


def test_enrichment_builds_a_versioned_canonical_retrieval_profile():
    product = enrich_product_semantics(_product())

    assert product.semantics is not None
    assert product.semantics.version == SEMANTIC_PROFILE_VERSION
    assert product.semantics.product_family == "kurta"
    assert product.semantics.audiences == ["women"]
    assert "mehndi" in product.semantics.occasions
    assert "embroidered" in product.semantics.attributes
    assert "bright festive yellow" in product.semantics.search_text
    assert product.semantics.formality == 3
    assert product.semantics.embellishment == "heavy"
    assert "lawn" in product.semantics.fabrics
    assert "festive" in product.semantics.festive_markers
    assert "description" in product.semantics.evidence_sources
    assert "search_text" not in product.model_dump()["semantics"]


def test_child_semantics_preserve_both_audience_and_age_scope():
    product = enrich_product_semantics(_product(is_kids=True, department="men"))

    assert product.semantics is not None
    assert product.semantics.audiences == ["men", "kids"]


def test_semantics_ignore_explicitly_negated_embellishment():
    product = enrich_product_semantics(_product(
        name="Plain Silk Kurta",
        description="A formal silk kurta without embellishment or embroidery.",
        tags=[],
        occasion=None,
    ))

    assert product.semantics is not None
    assert product.semantics.formality == 2
    assert product.semantics.embellishment == "none"


def test_activewear_semantics_are_explicit_and_versioned():
    product = enrich_product_semantics(_product(
        name="Dri-Fit Training Tee",
        description="Moisture-wicking performance fabric for workouts.",
        category="Activewear",
        tags=["training", "performance"],
        occasion=None,
    ))

    assert product.semantics is not None
    assert product.semantics.version == SEMANTIC_PROFILE_VERSION
    assert "activewear" in product.semantics.attributes
