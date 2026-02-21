"""add Enabled column to ReminderMessage and AutoDelete

Revision ID: 004
Revises: 003
Create Date: 2026-02-18
"""

import logging

import sqlalchemy as sa

# noinspection PyUnresolvedReferences
from alembic import op
from sqlalchemy import Boolean, Column

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)


def _column_exists(table: str, column: str) -> bool | None:
    """Return whether the column exists, or None if the table is absent."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in set(insp.get_table_names()):
        return None  # table absent — skip
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade():
    for table in ("ReminderMessage", "AutoDelete"):
        exists = _column_exists(table, "Enabled")
        if exists is None:
            log.info("Skipping %s.Enabled — table does not exist", table)
        elif exists:
            log.info("Skipping %s.Enabled — column already exists", table)
        else:
            op.add_column(table, Column("Enabled", Boolean, server_default="1"))


def downgrade():
    for table in ("ReminderMessage", "AutoDelete"):
        exists = _column_exists(table, "Enabled")
        if exists is None or not exists:
            log.info("Skipping %s.Enabled — column does not exist", table)
        else:
            op.drop_column(table, "Enabled")
