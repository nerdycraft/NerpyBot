"""application: add index on ApplicationSubmission.ReviewMessageId

Revision ID: 020
Revises: 019
Create Date: 2026-03-29

Adds a non-unique index on ApplicationSubmission(ReviewMessageId) to avoid
full-table scans in get_by_review_message().
"""

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationSubmission" in insp.get_table_names():
        existing_indexes = {i["name"] for i in insp.get_indexes("ApplicationSubmission")}
        if "ApplicationSubmission_ReviewMessageId" not in existing_indexes:
            op.create_index(
                "ApplicationSubmission_ReviewMessageId",
                "ApplicationSubmission",
                ["ReviewMessageId"],
            )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationSubmission" in insp.get_table_names():
        existing_indexes = {i["name"] for i in insp.get_indexes("ApplicationSubmission")}
        if "ApplicationSubmission_ReviewMessageId" in existing_indexes:
            op.drop_index("ApplicationSubmission_ReviewMessageId", table_name="ApplicationSubmission")
