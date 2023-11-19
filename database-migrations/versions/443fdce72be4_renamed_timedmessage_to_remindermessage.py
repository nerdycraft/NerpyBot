"""Renamed TimedMessage to ReminderMessage

Revision ID: 443fdce72be4
Revises: 121bb784c68a
Create Date: 2023-11-18 19:08:16.134795

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import Column, Text

# revision identifiers, used by Alembic.
revision: str = "443fdce72be4"
down_revision: Union[str, None] = "121bb784c68a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("TimedMessage", "ReminderMessage")
    op.add_column("ReminderMessage", Column("ChannelName", Text))


def downgrade() -> None:
    op.drop_column("ReminderMessage", "ChannelName")
    op.rename_table("ReminderMessage", "TimedMessage")
