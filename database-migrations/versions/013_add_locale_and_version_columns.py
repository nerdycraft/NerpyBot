"""wow: add locale JSON columns to CraftingRecipeCache and BoardVersion to CraftingBoardConfig

Revision ID: 013
Revises: 012
Create Date: 2026-03-15

Adds:
- CraftingRecipeCache.ItemNameLocales (JSON, nullable) — per-language item names
- CraftingRecipeCache.ItemClassNameLocales (JSON, nullable) — per-language item class names
- CraftingRecipeCache.ItemSubClassNameLocales (JSON, nullable) — per-language item subclass names
- CraftingBoardConfig.BoardVersion (Integer, server_default=1) — tracks board feature version
"""

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # ── CraftingRecipeCache ───────────────────────────────────────────────────
    if insp.has_table("CraftingRecipeCache"):
        existing = {c["name"] for c in insp.get_columns("CraftingRecipeCache")}
        new_cols = [
            ("ItemNameLocales", sa.JSON()),
            ("ItemClassNameLocales", sa.JSON()),
            ("ItemSubClassNameLocales", sa.JSON()),
        ]
        cols_to_add = [(name, typ) for name, typ in new_cols if name not in existing]

        if cols_to_add:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingRecipeCache") as batch_op:
                    for col_name, col_type in cols_to_add:
                        batch_op.add_column(sa.Column(col_name, col_type, nullable=True))
            else:
                for col_name, col_type in cols_to_add:
                    op.add_column("CraftingRecipeCache", sa.Column(col_name, col_type, nullable=True))

    # ── CraftingBoardConfig ───────────────────────────────────────────────────
    if insp.has_table("CraftingBoardConfig"):
        existing = {c["name"] for c in insp.get_columns("CraftingBoardConfig")}
        if "BoardVersion" not in existing:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingBoardConfig") as batch_op:
                    batch_op.add_column(sa.Column("BoardVersion", sa.Integer(), nullable=False, server_default="1"))
            else:
                op.add_column(
                    "CraftingBoardConfig",
                    sa.Column("BoardVersion", sa.Integer(), nullable=False, server_default="1"),
                )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # ── CraftingRecipeCache ───────────────────────────────────────────────────
    if insp.has_table("CraftingRecipeCache"):
        existing = {c["name"] for c in insp.get_columns("CraftingRecipeCache")}
        cols_to_drop = [
            c for c in ("ItemNameLocales", "ItemClassNameLocales", "ItemSubClassNameLocales") if c in existing
        ]
        if cols_to_drop:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingRecipeCache") as batch_op:
                    for col_name in cols_to_drop:
                        batch_op.drop_column(col_name)
            else:
                for col_name in cols_to_drop:
                    op.drop_column("CraftingRecipeCache", col_name)

    # ── CraftingBoardConfig ───────────────────────────────────────────────────
    if insp.has_table("CraftingBoardConfig"):
        existing = {c["name"] for c in insp.get_columns("CraftingBoardConfig")}
        if "BoardVersion" in existing:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingBoardConfig") as batch_op:
                    batch_op.drop_column("BoardVersion")
            else:
                op.drop_column("CraftingBoardConfig", "BoardVersion")
