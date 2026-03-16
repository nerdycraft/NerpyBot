"""wow: add BindType and ItemQuality columns to CraftingRecipeCache

Revision ID: 015
Revises: 014
Create Date: 2026-03-15

Adds:
- CraftingRecipeCache.BindType (String 20, nullable) — Blizzard binding type (ON_ACQUIRE, TO_ACCOUNT, ON_EQUIP, or None)
- CraftingRecipeCache.ItemQuality (String 20, nullable) — item quality tier (EPIC, RARE, COMMON, etc.)
"""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("CraftingRecipeCache"):
        return

    existing = {c["name"] for c in insp.get_columns("CraftingRecipeCache")}
    new_cols = [
        ("BindType", sa.String(20)),
        ("ItemQuality", sa.String(20)),
    ]
    cols_to_add = [(name, typ) for name, typ in new_cols if name not in existing]

    if not cols_to_add:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingRecipeCache") as batch_op:
            for col_name, col_type in cols_to_add:
                batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
    else:
        for col_name, col_type in cols_to_add:
            op.add_column("CraftingRecipeCache", sa.Column(col_name, col_type, nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if not insp.has_table("CraftingRecipeCache"):
        return

    existing = {c["name"] for c in insp.get_columns("CraftingRecipeCache")}
    cols_to_drop = [c for c in ("BindType", "ItemQuality") if c in existing]

    if not cols_to_drop:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingRecipeCache") as batch_op:
            for col_name in cols_to_drop:
                batch_op.drop_column(col_name)
    else:
        for col_name in cols_to_drop:
            op.drop_column("CraftingRecipeCache", col_name)
