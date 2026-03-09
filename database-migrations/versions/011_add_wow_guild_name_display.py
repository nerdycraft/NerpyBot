"""wow guild news: add WowGuildNameDisplay column

Revision ID: 011
Revises: 010
Create Date: 2026-03-09

Adds:
- WowGuildNewsConfig.WowGuildNameDisplay (nullable Unicode(100)) — the human-readable
  guild name as entered by the user (e.g. "New Haven").  WowGuildName remains the
  Blizzard API slug (e.g. "new-haven").  Existing rows get NULL; the schema helper
  falls back to WowGuildName for display so old trackers are unaffected.
"""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    tables = insp.get_table_names()

    if "WowGuildNewsConfig" not in tables:
        return

    existing = {c["name"] for c in insp.get_columns("WowGuildNewsConfig")}
    if "WowGuildNameDisplay" in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("WowGuildNewsConfig") as batch_op:
            batch_op.add_column(sa.Column("WowGuildNameDisplay", sa.Unicode(100), nullable=True))
    else:
        op.add_column("WowGuildNewsConfig", sa.Column("WowGuildNameDisplay", sa.Unicode(100), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "WowGuildNewsConfig" not in insp.get_table_names():
        return

    existing = {c["name"] for c in insp.get_columns("WowGuildNewsConfig")}
    if "WowGuildNameDisplay" not in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("WowGuildNewsConfig") as batch_op:
            batch_op.drop_column("WowGuildNameDisplay")
    else:
        op.drop_column("WowGuildNewsConfig", "WowGuildNameDisplay")
