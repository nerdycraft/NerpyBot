"""LeaveMessage.Message to UnicodeText for emoji support

Revision ID: 493f61588ed5
Revises: 443fdce72be4
Create Date: 2026-02-15 00:00:00.000000

"""

from alembic import op
from sqlalchemy import UnicodeText
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision: str = "493f61588ed5"
down_revision: str | None = "443fdce72be4"


def upgrade() -> None:
    try:
        op.alter_column("LeaveMessage", "Message", type_=UnicodeText)
    except OperationalError as ex:
        print(ex)


def downgrade() -> None:
    try:
        op.alter_column("LeaveMessage", "Message", type_=UnicodeText)
    except OperationalError as ex:
        print(ex)
