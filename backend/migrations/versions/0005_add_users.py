"""Add users table for real accounts (signup/login), and a nullable
user_id on wishlist_items so a shopper's wishlist and preferences persist
to their account instead of only the anonymous device that created them.

Revision ID: 0005_add_users
Revises: 0004_add_rad_store
Create Date: 2026-07-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0005_add_users"
down_revision = "0004_add_rad_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("preferred_size", sa.String(10), nullable=True),
        sa.Column("department", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.add_column("wishlist_items", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_wishlist_items_user_id", "wishlist_items", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_wishlist_items_user_id", "wishlist_items", ["user_id"])
    # Prevent the same account from having a product twice across devices,
    # without constraining anonymous (user_id IS NULL) rows at all.
    op.create_index(
        "uq_wishlist_items_user_product",
        "wishlist_items",
        ["user_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_wishlist_items_user_product", table_name="wishlist_items")
    op.drop_index("ix_wishlist_items_user_id", table_name="wishlist_items")
    op.drop_constraint("fk_wishlist_items_user_id", "wishlist_items", type_="foreignkey")
    op.drop_column("wishlist_items", "user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
