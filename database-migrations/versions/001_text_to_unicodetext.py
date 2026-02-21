"""convert Text/String columns to UnicodeText/Unicode for utf8mb4 emoji support

Revision ID: 001
Revises:
Create Date: 2026-02-15

"""

import logging
from typing import Sequence, Union

# noinspection PyUnresolvedReferences
from alembic import context, op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger(__name__)

# All table/column alterations for this migration. Every module is optional since
# any module can be disabled in config.yaml — only tables that actually exist in
# the database (created by the bot's create_all() on startup) will be altered.
ALTERATIONS = [
    # (table, column, unicode_type, ascii_type)
    # moderation
    ("AutoKicker", "ReminderMessage", sa.UnicodeText(), sa.Text()),
    # admin
    ("GuildPrefix", "Author", sa.Unicode(30), sa.String(30)),
    # reminder
    ("ReminderMessage", "Message", sa.UnicodeText(), sa.Text()),
    ("ReminderMessage", "Author", sa.Unicode(30), sa.String(30)),
    # raidplaner
    ("RaidTemplate", "Name", sa.Unicode(30), sa.String(30)),
    ("RaidTemplate", "Description", sa.Unicode(255), sa.String(255)),
    ("RaidEncounter", "Name", sa.Unicode(30), sa.String(30)),
    ("RaidEncounter", "Description", sa.Unicode(255), sa.String(255)),
    ("RaidEncounterRole", "Name", sa.Unicode(30), sa.String(30)),
    ("RaidEncounterRole", "Icon", sa.Unicode(30), sa.String(30)),
    ("RaidEncounterRole", "Description", sa.Unicode(255), sa.String(255)),
    ("RaidEvent", "Name", sa.Unicode(30), sa.String(30)),
    ("RaidEvent", "Description", sa.Unicode(255), sa.String(255)),
    ("RaidEvent", "Organizer", sa.Unicode(30), sa.String(30)),
    # reactionrole
    ("ReactionRoleEntry", "Emoji", sa.Unicode(100), sa.String(100)),
    # tagging
    ("Tag", "Name", sa.Unicode(30), sa.String(30)),
    ("Tag", "Author", sa.Unicode(30), sa.String(30)),
    ("TagEntry", "TextContent", sa.Unicode(255), sa.String(255)),
    # wow
    ("WowGuildNewsConfig", "WowGuildName", sa.Unicode(100), sa.String(100)),
    ("WowCharacterMounts", "CharacterName", sa.Unicode(50), sa.String(50)),
]


def _get_existing_tables() -> set[str] | None:
    """Return the set of table names present in the database, or None in offline mode."""
    if context.is_offline_mode():
        return None
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    # SQLite stores all text as Unicode internally — utf8mb4 is a MySQL-only concern.
    # ALTER COLUMN is also unsupported on SQLite without batch mode, so skip entirely.
    if not context.is_offline_mode() and bind.dialect.name == "sqlite":
        log.info("Skipping 001 upgrade — SQLite text is already Unicode")
        return

    existing = _get_existing_tables()
    for table, column, unicode_type, ascii_type in ALTERATIONS:
        if existing is not None and table not in existing:
            log.info("Skipping %s.%s — table does not exist", table, column)
            continue
        op.alter_column(table, column, type_=unicode_type, existing_type=ascii_type)


def downgrade() -> None:
    bind = op.get_bind()
    if not context.is_offline_mode() and bind.dialect.name == "sqlite":
        log.info("Skipping 001 downgrade — SQLite text is already Unicode")
        return

    existing = _get_existing_tables()
    for table, column, unicode_type, ascii_type in ALTERATIONS:
        if existing is not None and table not in existing:
            log.info("Skipping %s.%s — table does not exist", table, column)
            continue
        op.alter_column(table, column, type_=ascii_type, existing_type=unicode_type)
