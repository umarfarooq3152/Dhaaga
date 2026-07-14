"""Add department to brand_registry, seed 9 new menswear/streetwear brands.

Revision ID: 0002_brand_department
Revises: 0001_initial_schema
Create Date: 2026-07-14 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_brand_department"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

# slug -> department for the original 16 brands (best-effort classification;
# 'unisex' reserved for brands with a known, substantial menswear line).
EXISTING_BRAND_DEPARTMENTS = {
    "gul-ahmed": "unisex",
    "zellbury": "unisex",
    "junaid-jamshed": "unisex",
    "generation": "unisex",
    "outfitters": "unisex",
}

NEW_BRANDS = [
    {"name": "Ivar Clothing", "slug": "ivar-clothing", "domain": "ivarclothing.com"},
    {"name": "GROOVY", "slug": "groovy-pakistan", "domain": "groovypakistan.com"},
    {"name": "Outfit by DK", "slug": "outfit-by-dk", "domain": "outfitbydk.com"},
    {"name": "Kotton Fruit", "slug": "kotton-fruit", "domain": "www.kottonfruit.com"},
    {"name": "HavenWear", "slug": "havenwear", "domain": "havenwearpakistan.com"},
    {"name": "AWKWRDx", "slug": "awkwrdx", "domain": "www.awkwardxstore.com"},
    {"name": "Cougar", "slug": "cougar", "domain": "www.cougar.com.pk"},
    {"name": "ELO", "slug": "elo", "domain": "www.elo.shopping"},
    {"name": "The Hanger Pakistan", "slug": "the-hanger-pakistan", "domain": "thehangerpakistan.com"},
]


def upgrade() -> None:
    op.add_column(
        "brand_registry",
        sa.Column("department", sa.String(20), server_default="women", nullable=False),
    )

    for slug, department in EXISTING_BRAND_DEPARTMENTS.items():
        op.execute(
            f"UPDATE brand_registry SET department = '{department}' WHERE slug = '{slug}'"
        )

    for brand in NEW_BRANDS:
        op.execute(
            f"""
            INSERT INTO brand_registry (name, slug, domain, department, is_active)
            VALUES ('{brand["name"]}', '{brand["slug"]}', '{brand["domain"]}', 'men', true)
            """
        )


def downgrade() -> None:
    for brand in NEW_BRANDS:
        op.execute(f"DELETE FROM brand_registry WHERE slug = '{brand['slug']}'")
    op.drop_column("brand_registry", "department")
