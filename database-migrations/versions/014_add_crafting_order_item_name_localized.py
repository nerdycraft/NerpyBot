"""crafting order: add ItemNameLocalized column

Revision ID: 014
Revises: 013
Create Date: 2026-03-15

Adds:
- CraftingOrder.ItemNameLocalized (nullable Unicode 200) — locale-resolved item name stored at
  order creation time when using the cache-driven flow. Null for free-text orders or English guilds.
"""

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("CraftingOrder"):
        return

    existing = {c["name"] for c in insp.get_columns("CraftingOrder")}
    if "ItemNameLocalized" in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            batch_op.add_column(sa.Column("ItemNameLocalized", sa.Unicode(200), nullable=True))
    else:
        op.add_column("CraftingOrder", sa.Column("ItemNameLocalized", sa.Unicode(200), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("CraftingOrder"):
        return

    existing = {c["name"] for c in insp.get_columns("CraftingOrder")}
    if "ItemNameLocalized" not in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            batch_op.drop_column("ItemNameLocalized")
    else:
        op.drop_column("CraftingOrder", "ItemNameLocalized")
