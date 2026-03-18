"""wow: add CategoryNameLocales column to CraftingRecipeCache

Revision ID: 016
Revises: 015
Create Date: 2026-03-18

Adds:
- CraftingRecipeCache.CategoryNameLocales (JSON, nullable) — per-language category names
  fetched from profession_skill_tier for each non-English bot locale during sync.
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("CraftingRecipeCache"):
        existing = {c["name"] for c in insp.get_columns("CraftingRecipeCache")}
        if "CategoryNameLocales" not in existing:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingRecipeCache") as batch_op:
                    batch_op.add_column(sa.Column("CategoryNameLocales", sa.JSON(), nullable=True))
            else:
                op.add_column("CraftingRecipeCache", sa.Column("CategoryNameLocales", sa.JSON(), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if insp.has_table("CraftingRecipeCache"):
        existing = {c["name"] for c in insp.get_columns("CraftingRecipeCache")}
        if "CategoryNameLocales" in existing:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingRecipeCache") as batch_op:
                    batch_op.drop_column("CategoryNameLocales")
            else:
                op.drop_column("CraftingRecipeCache", "CategoryNameLocales")
