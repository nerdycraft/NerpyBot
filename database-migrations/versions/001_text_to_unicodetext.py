"""Text/UnicodeText migration — no-op after MySQL/MariaDB removal (kept for Alembic chain)

Revision ID: 001
Revises:
Create Date: 2026-02-15

"""

import logging
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger(__name__)


def upgrade() -> None:
    log.info("Skipping 001 — Text/UnicodeText conversion no longer needed (MySQL/MariaDB removed)")


def downgrade() -> None:
    log.info("Skipping 001 downgrade — Text/UnicodeText conversion no longer needed (MySQL/MariaDB removed)")
