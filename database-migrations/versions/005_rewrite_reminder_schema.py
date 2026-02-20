"""rewrite reminder schema: absolute timestamps + calendar scheduling

Revision ID: 005
Revises: 004
Create Date: 2026-02-18
"""

import sqlalchemy as sa

# noinspection PyUnresolvedReferences
from alembic import op
from sqlalchemy import Column, DateTime, Integer, String, Time, text

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "ReminderMessage" not in insp.get_table_names():
        return

    # Add new columns
    op.add_column("ReminderMessage", Column("NextFire", DateTime, nullable=True))
    op.add_column("ReminderMessage", Column("ScheduleType", String(10), nullable=True))
    op.add_column("ReminderMessage", Column("IntervalSeconds", Integer, nullable=True))
    op.add_column("ReminderMessage", Column("ScheduleTime", Time, nullable=True))
    op.add_column("ReminderMessage", Column("ScheduleDayOfWeek", Integer, nullable=True))
    op.add_column("ReminderMessage", Column("ScheduleDayOfMonth", Integer, nullable=True))
    op.add_column("ReminderMessage", Column("Timezone", String(50), nullable=True))

    # Migrate existing data: compute NextFire and ScheduleType from old columns
    dialect = conn.dialect.name
    if dialect == "sqlite":
        conn.execute(
            text("""
            UPDATE ReminderMessage
            SET NextFire = datetime(COALESCE(LastSend, CreateDate), '+' || (Minutes * 60) || ' seconds'),
                ScheduleType = CASE WHEN Repeat >= 1 THEN 'interval' ELSE 'once' END,
                IntervalSeconds = CASE WHEN Repeat >= 1 THEN Minutes * 60 ELSE NULL END
        """)
        )
    elif dialect == "postgresql":
        conn.execute(
            text("""
            UPDATE "ReminderMessage"
            SET "NextFire" = COALESCE("LastSend", "CreateDate") + make_interval(secs => "Minutes" * 60),
                "ScheduleType" = CASE WHEN "Repeat" >= 1 THEN 'interval' ELSE 'once' END,
                "IntervalSeconds" = CASE WHEN "Repeat" >= 1 THEN "Minutes" * 60 ELSE NULL END
        """)
        )
    else:
        # MySQL/MariaDB
        conn.execute(
            text("""
            UPDATE ReminderMessage
            SET NextFire = DATE_ADD(COALESCE(LastSend, CreateDate), INTERVAL (Minutes * 60) SECOND),
                ScheduleType = CASE WHEN `Repeat` >= 1 THEN 'interval' ELSE 'once' END,
                IntervalSeconds = CASE WHEN `Repeat` >= 1 THEN Minutes * 60 ELSE NULL END
        """)
        )

    # Make NextFire and ScheduleType NOT NULL, then drop old columns
    # Single batch_alter_table to avoid two full table copies on SQLite
    with op.batch_alter_table("ReminderMessage") as batch_op:
        batch_op.alter_column("NextFire", nullable=False)
        batch_op.alter_column("ScheduleType", nullable=False)
        batch_op.drop_column("Minutes")
        batch_op.drop_column("LastSend")
        batch_op.drop_column("Repeat")

    # Add index for efficient due-reminder queries
    op.create_index("ReminderMessage_NextFire_Enabled", "ReminderMessage", ["NextFire", "Enabled"])


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "ReminderMessage" not in insp.get_table_names():
        return

    op.drop_index("ReminderMessage_NextFire_Enabled", table_name="ReminderMessage")

    op.add_column("ReminderMessage", Column("Minutes", Integer, server_default="60"))
    op.add_column("ReminderMessage", Column("LastSend", DateTime, nullable=True))
    op.add_column("ReminderMessage", Column("Repeat", Integer, server_default="0"))

    # Best-effort reverse: IntervalSeconds back to Minutes, NextFire back to LastSend
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(
            text("""
            UPDATE "ReminderMessage"
            SET "Minutes" = COALESCE("IntervalSeconds" / 60, 60),
                "LastSend" = "NextFire",
                "Repeat" = CASE WHEN "ScheduleType" != 'once' THEN 1 ELSE 0 END
        """)
        )
    elif dialect in ("mysql", "mariadb"):
        conn.execute(
            text("""
            UPDATE ReminderMessage
            SET Minutes = COALESCE(IntervalSeconds / 60, 60),
                LastSend = NextFire,
                `Repeat` = CASE WHEN ScheduleType != 'once' THEN 1 ELSE 0 END
        """)
        )
    else:
        conn.execute(
            text("""
            UPDATE ReminderMessage
            SET Minutes = COALESCE(IntervalSeconds / 60, 60),
                LastSend = NextFire,
                "Repeat" = CASE WHEN ScheduleType != 'once' THEN 1 ELSE 0 END
        """)
        )

    with op.batch_alter_table("ReminderMessage") as batch_op:
        batch_op.drop_column("NextFire")
        batch_op.drop_column("ScheduleType")
        batch_op.drop_column("IntervalSeconds")
        batch_op.drop_column("ScheduleTime")
        batch_op.drop_column("ScheduleDayOfWeek")
        batch_op.drop_column("ScheduleDayOfMonth")
        batch_op.drop_column("Timezone")
