"""application: replace single role columns with multi-role junction table

Revision ID: 006
Revises: 005
Create Date: 2026-02-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import BigInteger, Column, Unicode, text

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationGuildConfig" not in insp.get_table_names():
        return

    # Fresh-install guard: create_all() already built the new schema without the old columns.
    existing_cols = {c["name"] for c in insp.get_columns("ApplicationGuildConfig")}
    if "ManagerRoleId" not in existing_cols and "ReviewerRoleId" not in existing_cols:
        return

    # Create junction table (may already exist on fresh install — guard with check)
    if "ApplicationGuildRole" not in insp.get_table_names():
        op.create_table(
            "ApplicationGuildRole",
            Column("GuildId", BigInteger, nullable=False),
            Column("RoleId", BigInteger, nullable=False),
            Column("RoleType", Unicode(10), nullable=False),
            sa.PrimaryKeyConstraint("GuildId", "RoleId"),
        )
        op.create_index(
            "ApplicationGuildRole_GuildId_Type",
            "ApplicationGuildRole",
            ["GuildId", "RoleType"],
        )

    # Migrate existing single-role data into the junction table
    dialect = conn.dialect.name
    if dialect == "sqlite":
        conn.execute(
            text(
                "INSERT OR IGNORE INTO ApplicationGuildRole (GuildId, RoleId, RoleType) "
                "SELECT GuildId, ManagerRoleId, 'manager' FROM ApplicationGuildConfig "
                "WHERE ManagerRoleId IS NOT NULL"
            )
        )
        conn.execute(
            text(
                "INSERT OR IGNORE INTO ApplicationGuildRole (GuildId, RoleId, RoleType) "
                "SELECT GuildId, ReviewerRoleId, 'reviewer' FROM ApplicationGuildConfig "
                "WHERE ReviewerRoleId IS NOT NULL"
            )
        )
    elif dialect == "postgresql":
        conn.execute(
            text(
                'INSERT INTO "ApplicationGuildRole" ("GuildId", "RoleId", "RoleType") '
                'SELECT "GuildId", "ManagerRoleId", \'manager\' FROM "ApplicationGuildConfig" '
                'WHERE "ManagerRoleId" IS NOT NULL '
                "ON CONFLICT DO NOTHING"
            )
        )
        conn.execute(
            text(
                'INSERT INTO "ApplicationGuildRole" ("GuildId", "RoleId", "RoleType") '
                'SELECT "GuildId", "ReviewerRoleId", \'reviewer\' FROM "ApplicationGuildConfig" '
                'WHERE "ReviewerRoleId" IS NOT NULL '
                "ON CONFLICT DO NOTHING"
            )
        )
    else:
        raise NotImplementedError(f"Unsupported dialect: {dialect}")

    # Drop old columns (batch_alter_table required for SQLite)
    with op.batch_alter_table("ApplicationGuildConfig") as batch_op:
        if "ManagerRoleId" in existing_cols:
            batch_op.drop_column("ManagerRoleId")
        if "ReviewerRoleId" in existing_cols:
            batch_op.drop_column("ReviewerRoleId")


def downgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    if "ApplicationGuildConfig" not in insp.get_table_names():
        return

    existing_cols = {c["name"] for c in insp.get_columns("ApplicationGuildConfig")}
    if "ManagerRoleId" in existing_cols:
        return  # Already at old schema

    # Re-add single-role columns
    with op.batch_alter_table("ApplicationGuildConfig") as batch_op:
        batch_op.add_column(Column("ManagerRoleId", BigInteger, nullable=True))
        batch_op.add_column(Column("ReviewerRoleId", BigInteger, nullable=True))

    # Best-effort: copy first manager/reviewer role per guild back to config columns
    dialect = conn.dialect.name
    if dialect == "sqlite":
        conn.execute(
            text(
                "UPDATE ApplicationGuildConfig SET ManagerRoleId = ("
                "  SELECT RoleId FROM ApplicationGuildRole"
                "  WHERE GuildId = ApplicationGuildConfig.GuildId AND RoleType = 'manager'"
                "  LIMIT 1"
                ")"
            )
        )
        conn.execute(
            text(
                "UPDATE ApplicationGuildConfig SET ReviewerRoleId = ("
                "  SELECT RoleId FROM ApplicationGuildRole"
                "  WHERE GuildId = ApplicationGuildConfig.GuildId AND RoleType = 'reviewer'"
                "  LIMIT 1"
                ")"
            )
        )
    elif dialect == "postgresql":
        conn.execute(
            text(
                'UPDATE "ApplicationGuildConfig" SET "ManagerRoleId" = ('
                '  SELECT "RoleId" FROM "ApplicationGuildRole"'
                '  WHERE "GuildId" = "ApplicationGuildConfig"."GuildId" AND "RoleType" = \'manager\''
                "  LIMIT 1"
                ")"
            )
        )
        conn.execute(
            text(
                'UPDATE "ApplicationGuildConfig" SET "ReviewerRoleId" = ('
                '  SELECT "RoleId" FROM "ApplicationGuildRole"'
                '  WHERE "GuildId" = "ApplicationGuildConfig"."GuildId" AND "RoleType" = \'reviewer\''
                "  LIMIT 1"
                ")"
            )
        )
    else:
        raise NotImplementedError(f"Unsupported dialect: {dialect}")

    if "ApplicationGuildRole" in insp.get_table_names():
        op.drop_index("ApplicationGuildRole_GuildId_Type", table_name="ApplicationGuildRole")
        op.drop_table("ApplicationGuildRole")
