"""reset postgresql sequences for all integer primary key tables

Revision ID: 007
Revises: 006
Create Date: 2026-03-08

Fixes UniqueViolation errors on INSERT caused by sequences being out of sync with
actual table data (e.g. after a SQLite → PostgreSQL migration that bypassed sequences).
"""

from alembic import op
from sqlalchemy import text

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

# All tables that use an auto-incremented integer column named "Id" as their primary key.
_TABLES_WITH_INTEGER_PK = [
    "ReactionRoleMessage",
    "ReactionRoleEntry",
    "RoleMapping",
    "ReminderMessage",
    "Tag",
    "TagEntry",
    "ApplicationForm",
    "ApplicationQuestion",
    "ApplicationSubmission",
    "ApplicationAnswer",
    "ApplicationVote",
    "ApplicationTemplate",
    "ApplicationTemplateQuestion",
    "AutoDelete",
    "WowGuildNewsConfig",
    "WowCharacterMounts",
    "CraftingBoardConfig",
    "CraftingRoleMapping",
    "CraftingOrder",
    "MusicPlaylist",
    "MusicPlaylistEntry",
]


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    insp = __import__("sqlalchemy").inspect(conn)
    existing_tables = set(insp.get_table_names())

    for table in _TABLES_WITH_INTEGER_PK:
        if table not in existing_tables:
            continue
        # setval(seq, max_id, is_called=true)  → next nextval() returns max_id + 1
        # setval(seq, 1,      is_called=false) → next nextval() returns 1 (empty table)
        conn.execute(
            text(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('"{table}"', 'Id'),
                    COALESCE((SELECT MAX("Id") FROM "{table}"), 1),
                    (SELECT COUNT(*) FROM "{table}") > 0
                )
                """
            )
        )


def downgrade():
    # Sequence resets are not reversible in a meaningful way.
    pass
