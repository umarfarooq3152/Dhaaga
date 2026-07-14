"""Seed brands into database — Phase 1."""

import json
import asyncio
from pathlib import Path
from app.db.models.brand import Brand


async def seed_brands(session):
    """Load brands from seed file and insert into database."""
    seed_file = Path(__file__).parent / "brands_seed.json"
    
    with open(seed_file) as f:
        brands_data = json.load(f)
    
    for brand_data in brands_data:
        brand = Brand(
            name=brand_data["name"],
            slug=brand_data["slug"],
            domain=brand_data["domain"],
            department=brand_data.get("department", "unisex"),
            is_active=True,
        )
        session.add(brand)
    
    await session.commit()
    print(f"✓ Seeded {len(brands_data)} brands")


if __name__ == "__main__":
    # To be run during Phase 1 migrations
    print("Run via: alembic/Phase 1 migrations")
