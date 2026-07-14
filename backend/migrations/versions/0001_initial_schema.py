"""Initial schema with 7 tables + seed data.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-07-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json
from pathlib import Path

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto extension for UUID generation
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    # brand_registry — 16 Tier-1 Shopify brands
    op.create_table(
        "brand_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    # devices — anonymous session tracking
    op.create_table(
        "devices",
        sa.Column("device_id", postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column("size", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("device_id"),
    )

    # wishlist_items — device_id + composite product_id (no FK to products table)
    op.create_table(
        "wishlist_items",
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("device_id", "product_id"),
    )

    # chat_messages — durable log; real-time state is in Redis
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("role IN ('user', 'assistant')"),
    )
    op.create_index("idx_chat_messages_session", "chat_messages", ["session_id", "created_at"])

    # session_events — analytics (north-star: turns-to-click)
    op.create_table(
        "session_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("product_id", sa.String(100), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('turn_fast_path', 'turn_llm_extraction', 'product_click', 'wishlist_add', 'brand_linkout')"
        ),
    )
    op.create_index("idx_session_events_session", "session_events", ["session_id", "created_at"])

    # query_intent_cache — LLM query dedup (24h TTL)
    op.create_table(
        "query_intent_cache",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("query_hash", sa.String(100), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("extracted_intent", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("query_hash"),
    )
    op.create_index("idx_query_cache_expires", "query_intent_cache", ["expires_at"])

    # collections — curated filter definitions (resolved live against product cache)
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.func.gen_random_uuid(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subtitle", sa.String(255), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("filter_definition", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed 16 brands
    seed_file = Path(__file__).parent.parent.parent / "seed" / "brands_seed.json"
    with open(seed_file) as f:
        brands_data = json.load(f)

    for brand in brands_data:
        op.execute(
            f"""
            INSERT INTO brand_registry (name, slug, domain, is_active)
            VALUES ('{brand["name"]}', '{brand["slug"]}', '{brand["domain"]}', true)
            """
        )

    # Seed 5 collections
    collections_file = Path(__file__).parent.parent.parent / "seed" / "collections_seed.json"
    with open(collections_file) as f:
        collections_data = json.load(f)

    for coll in collections_data:
        filter_def_json = json.dumps(coll["filter_definition"]).replace("'", "''")
        subtitle = coll.get("subtitle", "")
        description = coll.get("description", "")
        op.execute(
            f"""
            INSERT INTO collections (title, subtitle, description, filter_definition, is_active, sort_order)
            VALUES ('{coll["title"]}', '{subtitle}', '{description}', '{filter_def_json}'::jsonb, true, {coll.get("sort_order", 0)})
            """
        )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("collections")
    op.drop_table("query_intent_cache")
    op.drop_index("idx_session_events_session", table_name="session_events")
    op.drop_table("session_events")
    op.drop_index("idx_chat_messages_session", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("wishlist_items")
    op.drop_table("devices")
    op.drop_table("brand_registry")
    op.execute('DROP EXTENSION IF NOT EXISTS "pgcrypto"')
