"""Add LeaveMessage table

Revision ID: a1b2c3d4e5f6
Revises: 443fdce72be4
Create Date: 2025-02-12

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import BigInteger, Boolean, Column, Text
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "443fdce72be4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    try:
        op.create_table(
            "LeaveMessage",
            Column("GuildId", BigInteger, primary_key=True),
            Column("ChannelId", BigInteger, nullable=True),
            Column("Message", Text, nullable=True),
            Column("Enabled", Boolean, default=False),
        )
        op.create_index("LeaveMessage_GuildId", "LeaveMessage", ["GuildId"])
    except OperationalError as ex:
        print(ex)


def downgrade() -> None:
    try:
        op.drop_index("LeaveMessage_GuildId", table_name="LeaveMessage")
        op.drop_table("LeaveMessage")
    except OperationalError as ex:
        print(ex)
