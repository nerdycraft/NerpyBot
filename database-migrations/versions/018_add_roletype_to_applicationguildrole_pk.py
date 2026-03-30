"""application: add RoleType to ApplicationGuildRole primary key

Revision ID: 018
Revises: 017
Create Date: 2026-03-28

The original PK was (GuildId, RoleId), which prevented the same role from being
assigned both "manager" and "reviewer" types for the same guild.  The helper
methods already filter on (GuildId, RoleId, RoleType), so extending the PK to
include RoleType makes the schema consistent with the application logic.

WARNING - downgrade() risk: do not run downgrade() after data is live.
If rows with the same (GuildId, RoleId) but different RoleType values exist,
restoring the 2-column PK (GuildId, RoleId) will fail with a uniqueness
violation.  Deduplicate the table (keep one RoleType per GuildId+RoleId pair)
before attempting a downgrade.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import Unicode

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationGuildRole" not in insp.get_table_names():
        return

    # Check if PK already includes RoleType (fresh install has the new schema)
    pk_cols = {col for col in insp.get_pk_constraint("ApplicationGuildRole").get("constrained_columns", [])}
    if "RoleType" in pk_cols:
        return

    # SQLite: use batch_alter_table to recreate the table with the new PK
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table(
            "ApplicationGuildRole",
            recreate="always",
        ) as batch_op:
            batch_op.create_primary_key("pk_applicationguildrole", ["GuildId", "RoleId", "RoleType"])
        return

    # PostgreSQL: drop old PK constraint, add new one
    # First find the constraint name
    pk_constraint = insp.get_pk_constraint("ApplicationGuildRole")
    pk_name = pk_constraint.get("name") or "applicationguildrole_pkey"

    op.drop_constraint(pk_name, "ApplicationGuildRole", type_="primary")
    op.create_primary_key("pk_applicationguildrole", "ApplicationGuildRole", ["GuildId", "RoleId", "RoleType"])

    # Ensure RoleType is NOT NULL (should already be, but be explicit)
    op.alter_column(
        "ApplicationGuildRole",
        "RoleType",
        existing_type=Unicode(10),
        nullable=False,
    )


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationGuildRole" not in insp.get_table_names():
        return

    pk_cols = {col for col in insp.get_pk_constraint("ApplicationGuildRole").get("constrained_columns", [])}
    if "RoleType" not in pk_cols:
        return

    if conn.dialect.name == "sqlite":
        with op.batch_alter_table(
            "ApplicationGuildRole",
            recreate="always",
        ) as batch_op:
            batch_op.create_primary_key("pk_applicationguildrole", ["GuildId", "RoleId"])
        return

    pk_constraint = insp.get_pk_constraint("ApplicationGuildRole")
    pk_name = pk_constraint.get("name") or "pk_applicationguildrole"

    op.drop_constraint(pk_name, "ApplicationGuildRole", type_="primary")
    op.create_primary_key("applicationguildrole_pkey", "ApplicationGuildRole", ["GuildId", "RoleId"])
