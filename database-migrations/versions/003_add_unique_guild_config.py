"""add unique constraint for guild config

Revision ID: 003
Revises: 002
Create Date: 2026-02-16
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "WowGuildNewsConfig_Guild_Realm_Region",
        "WowGuildNewsConfig",
        ["GuildId", "WowGuildName", "WowRealmSlug", "Region"],
        unique=True,
    )


def downgrade():
    op.drop_index("WowGuildNewsConfig_Guild_Realm_Region", table_name="WowGuildNewsConfig")
