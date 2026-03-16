"""crafting order: add WowheadUrl column

Revision ID: 012
Revises: 011
Create Date: 2026-03-15

Adds:
- CraftingOrder.WowheadUrl (nullable Unicode 500) — Wowhead item/spell URL stored at order creation time
  when using the cache-driven flow. Null for orders created via free-text.
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "CraftingOrder" not in insp.get_table_names():
        return

    existing = {c["name"] for c in insp.get_columns("CraftingOrder")}

    if "WowheadUrl" in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            batch_op.add_column(sa.Column("WowheadUrl", sa.Unicode(500), nullable=True))
    else:
        op.add_column("CraftingOrder", sa.Column("WowheadUrl", sa.Unicode(500), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "CraftingOrder" not in insp.get_table_names():
        return

    existing = {c["name"] for c in insp.get_columns("CraftingOrder")}

    if "WowheadUrl" not in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            batch_op.drop_column("WowheadUrl")
    else:
        op.drop_column("CraftingOrder", "WowheadUrl")
