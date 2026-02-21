"""add AccountGroupData to WowGuildNewsConfig

Revision ID: 002
Revises: 001
Create Date: 2026-02-16

"""

import logging
from typing import Sequence, Union

# noinspection PyUnresolvedReferences
from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger(__name__)

TABLE = "WowGuildNewsConfig"
COLUMN = "AccountGroupData"


def _column_exists() -> bool | None:
    """Return whether the column exists in the table, or None in offline mode."""
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if TABLE not in set(insp.get_table_names()):
        return None  # table absent — skip
    return COLUMN in {c["name"] for c in insp.get_columns(TABLE)}


def upgrade() -> None:
    exists = _column_exists()
    if exists is None:
        log.info("Skipping %s.%s — table does not exist", TABLE, COLUMN)
        return
    if exists:
        log.info("Skipping %s.%s — column already exists", TABLE, COLUMN)
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True, server_default="{}"))


def downgrade() -> None:
    exists = _column_exists()
    if exists is None or not exists:
        log.info("Skipping %s.%s — column does not exist", TABLE, COLUMN)
        return
    op.drop_column(TABLE, COLUMN)
