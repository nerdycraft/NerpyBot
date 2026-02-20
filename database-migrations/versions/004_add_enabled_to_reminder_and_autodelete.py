"""add Enabled column to ReminderMessage and AutoDelete

Revision ID: 004
Revises: 003
Create Date: 2026-02-18
"""

# noinspection PyUnresolvedReferences
from alembic import op
from sqlalchemy import Boolean, Column

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ReminderMessage", Column("Enabled", Boolean, server_default="1"))
    op.add_column("AutoDelete", Column("Enabled", Boolean, server_default="1"))


def downgrade():
    op.drop_column("ReminderMessage", "Enabled")
    op.drop_column("AutoDelete", "Enabled")
