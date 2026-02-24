# -*- coding: utf-8 -*-
"""Shared pytest fixtures for NerpyBot test suite"""

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add NerdyPy to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "NerdyPy"))

from utils.database import BASE


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Import all models to ensure they're registered with BASE.metadata
    from models.application import (  # noqa: F401
        ApplicationForm,
        ApplicationQuestion,
        ApplicationSubmission,
        ApplicationAnswer,
        ApplicationVote,
        ApplicationGuildConfig,
        ApplicationTemplate,
        ApplicationTemplateQuestion,
    )
    from models.reminder import ReminderMessage  # noqa: F401
    from models.tagging import Tag, TagEntry  # noqa: F401
    from models.admin import BotModeratorRole, PermissionSubscriber, GuildLanguageConfig  # noqa: F401
    from models.leavemsg import LeaveMessage  # noqa: F401
    from models.moderation import AutoDelete, AutoKicker  # noqa: F401
    from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage  # noqa: F401
    from models.rolemanage import RoleMapping  # noqa: F401
    from models.wow import (  # noqa: F401
        WowGuildNewsConfig,
        WowCharacterMounts,
        CraftingBoardConfig,
        CraftingRoleMapping,
        CraftingRecipeCache,
        CraftingOrder,
    )

    BASE.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Create a new database session for testing."""
    _session = sessionmaker(bind=db_engine)
    session = _session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def mock_log():
    """Mock logger that can be attached to bot."""
    log = MagicMock()
    log.info = MagicMock()
    log.debug = MagicMock()
    log.warning = MagicMock()
    log.error = MagicMock()
    return log


@pytest.fixture
def mock_bot(db_session, mock_log):
    """Create a mock bot with session_scope context manager."""
    bot = MagicMock()
    bot.log = mock_log

    @contextmanager
    def session_scope():
        yield db_session

    bot.session_scope = session_scope
    bot.config = MagicMock()

    return bot


@pytest.fixture
def mock_member():
    """Create a mock discord.Member."""
    member = MagicMock()
    member.id = 123456789
    member.name = "TestUser"
    member.display_name = "Test User"
    member.mention = "<@123456789>"
    member.voice = MagicMock()
    member.voice.channel = MagicMock()
    member.voice.channel.guild = MagicMock()
    member.voice.channel.guild.id = 987654321
    return member


@pytest.fixture
def mock_guild():
    """Create a mock discord.Guild."""
    guild = MagicMock()
    guild.id = 987654321
    guild.name = "Test Guild"
    return guild


@pytest.fixture
def mock_channel():
    """Create a mock discord.TextChannel."""
    channel = MagicMock()
    channel.id = 111222333
    channel.name = "test-channel"
    channel.send = AsyncMock()
    return channel


@pytest.fixture
def mock_message(mock_member, mock_channel, mock_guild):
    """Create a mock discord.Message."""
    message = MagicMock()
    message.id = 444555666
    message.author = mock_member
    message.channel = mock_channel
    message.guild = mock_guild
    message.content = "test message"
    return message


@pytest.fixture
def mock_context(mock_bot, mock_member, mock_guild, mock_channel, mock_message):
    """Create a mock discord Context for command testing."""
    ctx = MagicMock()
    ctx.bot = mock_bot
    ctx.author = mock_member
    ctx.guild = mock_guild
    ctx.channel = mock_channel
    ctx.message = mock_message
    ctx.send = AsyncMock()
    ctx.send_help = AsyncMock()
    ctx.typing = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))
    ctx.invoked_subcommand = None
    return ctx


@pytest.fixture
def mock_interaction(mock_bot, mock_member, mock_guild, mock_channel):
    """Create a mock discord Interaction for slash command testing."""
    interaction = MagicMock()
    interaction.client = mock_bot
    interaction.user = mock_member
    interaction.guild = mock_guild
    interaction.guild_id = mock_guild.id
    interaction.channel = mock_channel
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.command = MagicMock()
    interaction.command.qualified_name = "test"
    return interaction


@pytest.fixture
def mock_user():
    """Create a mock discord.User for DM conversations."""
    user = MagicMock()
    user.id = 123456789
    user.name = "TestUser"
    user.send = AsyncMock()
    return user
