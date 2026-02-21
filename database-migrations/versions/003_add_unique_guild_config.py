"""add unique constraint for guild config

Revision ID: 003
Revises: 002
Create Date: 2026-02-16
"""

import logging

import sqlalchemy as sa

# noinspection PyUnresolvedReferences
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

TABLE = "WowGuildNewsConfig"
INDEX = "WowGuildNewsConfig_Guild_Realm_Region"


def _index_exists() -> bool | None:
    """Return whether the index exists, or None if the table is absent."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if TABLE not in set(insp.get_table_names()):
        return None  # table absent — skip
    return INDEX in {idx["name"] for idx in insp.get_indexes(TABLE)}


def upgrade():
    exists = _index_exists()
    if exists is None:
        log.info("Skipping %s — table does not exist", INDEX)
        return
    if exists:
        log.info("Skipping %s — index already exists", INDEX)
        return
    op.create_index(INDEX, TABLE, ["GuildId", "WowGuildName", "WowRealmSlug", "Region"], unique=True)


def downgrade():
    exists = _index_exists()
    if exists is None or not exists:
        log.info("Skipping %s — index does not exist", INDEX)
        return
    op.drop_index(INDEX, table_name=TABLE)
