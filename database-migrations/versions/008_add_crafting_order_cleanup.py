"""crafting order: add MessageDeleteAt and ThreadCleanupDelayHours

Revision ID: 008
Revises: 007
Create Date: 2026-03-08

Adds:
- CraftingOrder.MessageDeleteAt (nullable DateTime) — set when a DM-fallback thread is
  created so the background cleanup task knows when to delete the anchored message.
- CraftingBoardConfig.ThreadCleanupDelayHours (Integer, default 24) — per-guild
  configurable delay before the anchored order message is deleted.
"""

import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    tables = insp.get_table_names()

    # ── CraftingBoardConfig.ThreadCleanupDelayHours ────────────────────────────
    if "CraftingBoardConfig" in tables:
        existing = {c["name"] for c in insp.get_columns("CraftingBoardConfig")}
        if "ThreadCleanupDelayHours" not in existing:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingBoardConfig") as batch_op:
                    batch_op.add_column(
                        sa.Column("ThreadCleanupDelayHours", sa.Integer(), nullable=False, server_default="24")
                    )
            else:
                op.add_column(
                    "CraftingBoardConfig",
                    sa.Column("ThreadCleanupDelayHours", sa.Integer(), nullable=False, server_default="24"),
                )

    # ── CraftingOrder.MessageDeleteAt ──────────────────────────────────────────
    if "CraftingOrder" in tables:
        existing = {c["name"] for c in insp.get_columns("CraftingOrder")}
        if "MessageDeleteAt" not in existing:
            if conn.dialect.name == "sqlite":
                with op.batch_alter_table("CraftingOrder") as batch_op:
                    batch_op.add_column(sa.Column("MessageDeleteAt", sa.DateTime(), nullable=True))
            else:
                op.add_column("CraftingOrder", sa.Column("MessageDeleteAt", sa.DateTime(), nullable=True))


def downgrade():
    conn = op.get_bind()

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("CraftingOrder") as batch_op:
            batch_op.drop_column("MessageDeleteAt")
        with op.batch_alter_table("CraftingBoardConfig") as batch_op:
            batch_op.drop_column("ThreadCleanupDelayHours")
    else:
        op.drop_column("CraftingOrder", "MessageDeleteAt")
        op.drop_column("CraftingBoardConfig", "ThreadCleanupDelayHours")
