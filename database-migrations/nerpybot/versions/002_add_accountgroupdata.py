"""add AccountGroupData to WowGuildNewsConfig

Revision ID: 002
Revises: 001
Create Date: 2026-02-16

"""

import logging
from typing import Sequence, Union

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


def _table_exists() -> bool | None:
    """Return whether the table exists, or None in offline mode."""
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    return TABLE in set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    exists = _table_exists()
    if exists is not None and not exists:
        log.info("Skipping %s.%s — table does not exist", TABLE, COLUMN)
        return
    op.add_column(TABLE, sa.Column(COLUMN, sa.Text(), nullable=True, server_default="{}"))


def downgrade() -> None:
    exists = _table_exists()
    if exists is not None and not exists:
        log.info("Skipping %s.%s — table does not exist", TABLE, COLUMN)
        return
    op.drop_column(TABLE, COLUMN)
