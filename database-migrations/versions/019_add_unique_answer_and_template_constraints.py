"""application: add unique constraints on ApplicationAnswer and ApplicationTemplate

Revision ID: 019
Revises: 018
Create Date: 2026-03-29

Adds:
- Unique index on ApplicationAnswer(SubmissionId, QuestionId) to prevent
  duplicate answers for the same question in a single submission.
- Unique index on ApplicationTemplate(Name, GuildId) to prevent duplicate
  template names per guild (NULL GuildId is treated as distinct by both
  SQLite and PostgreSQL, so built-in templates are unaffected).

Both upgrades deduplicate existing rows (keeping the lowest Id) before
creating the index and guard against a schema that is already up-to-date
(i.e. fresh installs where create_all() already applied the latest model).
"""

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # ── ApplicationAnswer unique index ───────────────────────────────────
    if "ApplicationAnswer" in insp.get_table_names():
        existing_indexes = {i["name"] for i in insp.get_indexes("ApplicationAnswer")}
        if "ApplicationAnswer_SubmissionId_QuestionId" not in existing_indexes:
            # Remove duplicate (SubmissionId, QuestionId) rows, keeping lowest Id.
            conn.execute(
                sa.text(
                    """
                    DELETE FROM "ApplicationAnswer"
                    WHERE "Id" NOT IN (
                        SELECT MIN("Id")
                        FROM "ApplicationAnswer"
                        GROUP BY "SubmissionId", "QuestionId"
                    )
                    """
                )
            )
            op.create_index(
                "ApplicationAnswer_SubmissionId_QuestionId",
                "ApplicationAnswer",
                ["SubmissionId", "QuestionId"],
                unique=True,
            )

    # ── ApplicationTemplate unique index ─────────────────────────────────
    if "ApplicationTemplate" in insp.get_table_names():
        existing_indexes = {i["name"] for i in insp.get_indexes("ApplicationTemplate")}
        if "ApplicationTemplate_Name_GuildId" not in existing_indexes:
            # Remove duplicate (Name, GuildId) rows, keeping lowest Id.
            # NULL GuildId is handled correctly: NULL != NULL in SQL, so
            # built-in templates (GuildId IS NULL) are each compared individually.
            if conn.dialect.name == "sqlite":
                conn.execute(
                    sa.text(
                        """
                        DELETE FROM "ApplicationTemplate"
                        WHERE "Id" NOT IN (
                            SELECT MIN("Id")
                            FROM "ApplicationTemplate"
                            GROUP BY "Name", COALESCE("GuildId", -1)
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    sa.text(
                        """
                        DELETE FROM "ApplicationTemplate"
                        WHERE "Id" NOT IN (
                            SELECT MIN("Id")
                            FROM "ApplicationTemplate"
                            GROUP BY "Name", "GuildId"
                        )
                        """
                    )
                )
            op.create_index(
                "ApplicationTemplate_Name_GuildId",
                "ApplicationTemplate",
                ["Name", "GuildId"],
                unique=True,
            )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationTemplate" in insp.get_table_names():
        existing_indexes = {i["name"] for i in insp.get_indexes("ApplicationTemplate")}
        if "ApplicationTemplate_Name_GuildId" in existing_indexes:
            op.drop_index("ApplicationTemplate_Name_GuildId", table_name="ApplicationTemplate")

    if "ApplicationAnswer" in insp.get_table_names():
        existing_indexes = {i["name"] for i in insp.get_indexes("ApplicationAnswer")}
        if "ApplicationAnswer_SubmissionId_QuestionId" in existing_indexes:
            op.drop_index("ApplicationAnswer_SubmissionId_QuestionId", table_name="ApplicationAnswer")
