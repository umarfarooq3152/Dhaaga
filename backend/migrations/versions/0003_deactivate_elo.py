"""Deactivate ELO — it's a general multi-category marketplace (kitchen
tongs, BBQ tools, home goods mixed in with apparel), not a clothing/outfit
retailer, so it doesn't fit an outfit-discovery catalog. Discovered via a
real search result showing a "Stainless Steel BBQ Kitchen Tong" alongside
actual clothing items.

Revision ID: 0003_deactivate_elo
Revises: 0002_brand_department
Create Date: 2026-07-14 14:15:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_deactivate_elo"
down_revision = "0002_brand_department"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE brand_registry SET is_active = false WHERE slug = 'elo'")


def downgrade() -> None:
    op.execute("UPDATE brand_registry SET is_active = true WHERE slug = 'elo'")
