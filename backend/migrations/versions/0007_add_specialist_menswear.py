"""Add specialist Shopify menswear catalogs for eastern formal discovery."""

from alembic import op


revision = "0007_specialist_menswear"
down_revision = "0006_generation_department"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These are additive and idempotent. Stores that temporarily reject the
    # public products endpoint remain harmlessly cached as empty until a later
    # refresh; they do not affect the existing 25 catalogs.
    stores = (
        ("FS Vestiario", "fs-vestiario", "fsvestiario.com", "men"),
        (
            "Hamza Collection Menswear",
            "hamza-collection-menswear",
            "hamzacollectionmenswearbytayyyab.com",
            "men",
        ),
        (
            "Republic by Omar Farooq",
            "republic-omar-farooq",
            "republic-menswear.myshopify.com",
            "men",
        ),
    )
    for name, slug, domain, department in stores:
        op.execute(
            """
            INSERT INTO brand_registry (name, slug, domain, department, is_active)
            VALUES ('%s', '%s', '%s', '%s', true)
            ON CONFLICT (slug) DO UPDATE
            SET name = EXCLUDED.name,
                domain = EXCLUDED.domain,
                department = EXCLUDED.department,
                is_active = true
            """ % (name, slug, domain, department)
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM brand_registry WHERE slug IN "
        "('fs-vestiario', 'hamza-collection-menswear', 'republic-omar-farooq')"
    )
