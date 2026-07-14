"""Post-migration seeding — run after 0001_initial_schema."""

from alembic import op
import json
from pathlib import Path
from sqlalchemy import text


def seed_brands_and_collections():
    """Seed 16 brands and 5 collections."""
    bind = op.get_bind()

    # Load brands seed
    seed_file = Path(__file__).parent.parent.parent / "seed" / "brands_seed.json"
    with open(seed_file) as f:
        brands_data = json.load(f)

    # Insert brands
    for brand in brands_data:
        op.execute(
            text("""
                INSERT INTO brand_registry (name, slug, domain, is_active)
                VALUES (:name, :slug, :domain, :is_active)
            """),
            {
                "name": brand["name"],
                "slug": brand["slug"],
                "domain": brand["domain"],
                "is_active": True,
            },
        )

    # Load collections seed
    collections_file = Path(__file__).parent.parent.parent / "seed" / "collections_seed.json"
    with open(collections_file) as f:
        collections_data = json.load(f)

    # Insert collections
    for coll in collections_data:
        op.execute(
            text("""
                INSERT INTO collections (title, subtitle, description, filter_definition, is_active, sort_order)
                VALUES (:title, :subtitle, :description, :filter_definition::jsonb, :is_active, :sort_order)
            """),
            {
                "title": coll["title"],
                "subtitle": coll.get("subtitle"),
                "description": coll.get("description"),
                "filter_definition": json.dumps(coll["filter_definition"]),
                "is_active": True,
                "sort_order": coll.get("sort_order", 0),
            },
        )
