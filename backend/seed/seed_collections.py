"""Seed collections into database — Phase 1."""

import json
from pathlib import Path
from app.db.models.collections import Collection


async def seed_collections(session):
    """Load collections from seed file and insert into database."""
    seed_file = Path(__file__).parent / "collections_seed.json"
    
    with open(seed_file) as f:
        collections_data = json.load(f)
    
    for coll_data in collections_data:
        collection = Collection(
            title=coll_data["title"],
            subtitle=coll_data.get("subtitle"),
            description=coll_data.get("description"),
            filter_definition=coll_data["filter_definition"],
            is_active=True,
            sort_order=coll_data.get("sort_order", 0),
        )
        session.add(collection)
    
    await session.commit()
    print(f"✓ Seeded {len(collections_data)} collections")


if __name__ == "__main__":
    # To be run during Phase 1 migrations
    print("Run via: alembic/Phase 1 migrations")
