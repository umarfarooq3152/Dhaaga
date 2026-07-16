"""Add Rad Store — verified Shopify menswear athleisure brand (sweatshirts,
tees, cargo pants, trousers), added after live-testing menswear search
coverage. Verified via direct /products.json fetch before adding: 100
products sampled, all "Tops"/"Bottoms" apparel, Rs. 960-3500 price range.

Revision ID: 0004_add_rad_store
Revises: 0003_deactivate_elo
Create Date: 2026-07-15 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_add_rad_store"
down_revision = "0003_deactivate_elo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO brand_registry (name, slug, domain, department, is_active)
        VALUES ('Rad Store', 'rad-store', 'radstore.pk', 'men', true)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            domain = EXCLUDED.domain,
            department = 'men',
            is_active = true
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM brand_registry WHERE slug = 'rad-store'")
