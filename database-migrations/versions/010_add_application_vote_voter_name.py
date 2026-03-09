"""application vote: persist voter display name

Revision ID: 010
Revises: 009
Create Date: 2026-03-09

Adds:
- ApplicationVote.VoterName (nullable Unicode(100)) — display name of the reviewer
  who cast the vote, stored at vote time so the web dashboard can show who approved/denied
  a submission even after the reviewer leaves the server.
"""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    tables = insp.get_table_names()

    if "ApplicationVote" not in tables:
        return

    existing = {c["name"] for c in insp.get_columns("ApplicationVote")}
    if "VoterName" in existing:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("ApplicationVote") as batch_op:
            batch_op.add_column(sa.Column("VoterName", sa.Unicode(100), nullable=True))
    else:
        op.add_column("ApplicationVote", sa.Column("VoterName", sa.Unicode(100), nullable=True))


def downgrade():
    conn = op.get_bind()

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("ApplicationVote") as batch_op:
            batch_op.drop_column("VoterName")
    else:
        op.drop_column("ApplicationVote", "VoterName")
