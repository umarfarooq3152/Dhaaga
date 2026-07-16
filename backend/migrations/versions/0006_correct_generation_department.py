"""Correct Generation's catalog audience to women.

Revision ID: 0006_generation_department
Revises: 0005_add_users
Create Date: 2026-07-15 11:20:00.000000
"""

from alembic import op


revision = "0006_generation_department"
down_revision = "0005_add_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE brand_registry SET department = 'women' WHERE slug = 'generation'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE brand_registry SET department = 'unisex' WHERE slug = 'generation'"
    )
