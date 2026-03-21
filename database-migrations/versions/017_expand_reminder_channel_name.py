"""reminder: expand ChannelName column from String(30) to String(100)

Revision ID: 017
Revises: 016
Create Date: 2026-03-21

Discord channel names can be up to 100 characters. The original String(30) was
too short and would cause IntegrityErrors on PostgreSQL for long channel names.
SQLite does not enforce VARCHAR length limits, so this migration skips it.
"""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if conn.dialect.name == "sqlite":
        return

    if insp.has_table("ReminderMessage"):
        cols = {c["name"]: c for c in insp.get_columns("ReminderMessage")}
        col = cols.get("ChannelName")
        if col is not None and getattr(col["type"], "length", None) != 100:
            op.alter_column(
                "ReminderMessage",
                "ChannelName",
                type_=sa.String(100),
                existing_type=col["type"],
                existing_nullable=True,
            )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if conn.dialect.name == "sqlite":
        return

    if insp.has_table("ReminderMessage"):
        cols = {c["name"]: c for c in insp.get_columns("ReminderMessage")}
        col = cols.get("ChannelName")
        if col is not None and getattr(col["type"], "length", None) != 30:
            op.alter_column(
                "ReminderMessage",
                "ChannelName",
                type_=sa.String(30),
                existing_type=col["type"],
                existing_nullable=True,
            )
