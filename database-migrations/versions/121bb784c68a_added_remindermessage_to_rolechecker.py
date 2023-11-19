"""Added ReminderMessage to RoleChecker

Revision ID: 121bb784c68a
Revises: 
Create Date: 2023-08-26 12:11:19.204787

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import Column, Text

# revision identifiers, used by Alembic.
revision: str = "121bb784c68a"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("RoleChecker", Column("ReminderMessage", Text))


def downgrade() -> None:
    op.drop_column("RoleChecker", "ReminderMessage")
