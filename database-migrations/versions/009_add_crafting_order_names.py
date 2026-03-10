"""crafting order: persist creator and crafter display names

Revision ID: 009
Revises: 008
Create Date: 2026-03-09

Adds:
- CraftingOrder.CreatorName (nullable UnicodeText) — display name of the order creator at creation time.
- CraftingOrder.CrafterName (nullable UnicodeText) — display name of the crafter when they accept; cleared on drop.
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    tables = insp.get_table_names()

    if "CraftingOrder" not in tables:
        return

    existing = {c["name"] for c in insp.get_columns("CraftingOrder")}

    if "CreatorName" in existing and "CrafterName" in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            if "CreatorName" not in existing:
                batch_op.add_column(sa.Column("CreatorName", sa.UnicodeText(), nullable=True))
            if "CrafterName" not in existing:
                batch_op.add_column(sa.Column("CrafterName", sa.UnicodeText(), nullable=True))
    else:
        if "CreatorName" not in existing:
            op.add_column("CraftingOrder", sa.Column("CreatorName", sa.UnicodeText(), nullable=True))
        if "CrafterName" not in existing:
            op.add_column("CraftingOrder", sa.Column("CrafterName", sa.UnicodeText(), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "CraftingOrder" not in insp.get_table_names():
        return

    existing = {c["name"] for c in insp.get_columns("CraftingOrder")}
    if "CreatorName" not in existing and "CrafterName" not in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            if "CrafterName" in existing:
                batch_op.drop_column("CrafterName")
            if "CreatorName" in existing:
                batch_op.drop_column("CreatorName")
    else:
        if "CrafterName" in existing:
            op.drop_column("CraftingOrder", "CrafterName")
        if "CreatorName" in existing:
            op.drop_column("CraftingOrder", "CreatorName")
