"""Added ReminderMessage to RoleChecker

Revision ID: 121bb784c68a
Revises:
Create Date: 2023-08-26 12:11:19.204787

"""

from alembic import op
from sqlalchemy import Column, Text
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision: str = "121bb784c68a"
down_revision: str | None = None


def upgrade() -> None:
    try:
        op.add_column("RoleChecker", Column("ReminderMessage", Text))
    except OperationalError as ex:
        print(ex)


def downgrade() -> None:
    try:
        op.drop_column("RoleChecker", "ReminderMessage")
    except OperationalError as ex:
        print(ex)
