# -*- coding: utf-8 -*-
"""Shared DB engine factory for NerpyBot test suites."""

import sys
from pathlib import Path

# Ensure NerdyPy is on sys.path for model imports
sys.path.insert(0, str(Path(__file__).parent.parent / "NerdyPy"))

from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

# Import ALL models from both conftest files (union) so SQLAlchemy registers
# them with BASE.metadata before create_all() is called.
from models.application import (  # noqa: F401
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationGuildRole,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    ApplicationVote,
)
from models.guild import GuildLanguageConfig  # noqa: F401
from models.leavemsg import LeaveMessage  # noqa: F401
from models.moderation import AutoDelete, AutoKicker  # noqa: F401
from models.music import Playlist, PlaylistEntry  # noqa: F401
from models.permissions import BotModeratorRole, PermissionSubscriber  # noqa: F401
from models.premium import PremiumUser  # noqa: F401
from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage  # noqa: F401
from models.reminder import ReminderMessage  # noqa: F401
from models.rolemanage import RoleMapping  # noqa: F401
from models.twitch import TwitchEventSubSubscription, TwitchNotifications  # noqa: F401
from models.wow import (  # noqa: F401
    CraftingBoardConfig,
    CraftingOrder,
    CraftingRecipeCache,
    CraftingRoleMapping,
    WowCharacterMounts,
    WowGuildNewsConfig,
)
from utils.database import BASE


def create_test_engine():
    """Create an in-memory SQLite engine with all models registered."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, _connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    BASE.metadata.create_all(engine)
    return engine
