# -*- coding: utf-8 -*-
"""Shared pytest fixtures for NerpyBot test suite"""

import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

# Add NerdyPy and tests/ to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / "NerdyPy"))
sys.path.insert(0, str(Path(__file__).parent))

from db_helpers import create_test_engine


@pytest.fixture(autouse=True)
def clear_bot_caches():
    """Clear bot-side in-process TTL caches between tests.

    Module-level TTLCache singletons live for the entire process lifetime.
    Tests that use function-scoped DB sessions trigger rollback() on cleanup,
    which expires SQLAlchemy ORM objects. A subsequent test that hits the warm
    cache gets expired+detached objects, raising DetachedInstanceError or
    "no such table" errors from lazy-load attempts on a different in-memory DB.
    """
    from models.wow import invalidate_recipe_cache
    from utils.cache import _autocomplete_cache

    _autocomplete_cache.clear()
    invalidate_recipe_cache()
    yield


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_test_engine()
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
    from utils.cache import GuildConfigCache
    from utils.strings import get_string

    bot = MagicMock()
    bot.log = mock_log

    @contextmanager
    def session_scope():
        yield db_session

    bot.session_scope = session_scope
    bot.config = MagicMock()

    # Wire up a real GuildConfigCache backed by the test DB session so that
    # tests inserting GuildLanguageConfig/BotModeratorRole rows see correct results.
    db_session.close = MagicMock()  # prevent cache from closing the shared test session
    _factory = MagicMock(return_value=db_session)
    _cache = GuildConfigCache()
    bot.guild_cache = _cache
    bot.SESSION = _factory
    bot.get_guild_language = lambda guild_id: (
        "en" if guild_id is None else _cache.get_guild_language(guild_id, _factory)
    )
    bot.get_localized_string = lambda guild_id, key, **kwargs: get_string(
        bot.get_guild_language(guild_id), key, **kwargs
    )

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
def mock_voice_client():
    """Create a mock discord.VoiceClient connected to a guild voice channel."""
    vc_guild = MagicMock()
    vc_guild.id = 12345
    vc_guild.name = "Test Guild"
    vc_channel = MagicMock()
    vc_channel.id = 67890
    vc_channel.name = "General Voice"
    vc = MagicMock()
    vc.guild = vc_guild
    vc.channel = vc_channel
    return vc


@pytest.fixture
def mock_user():
    """Create a mock discord.User for DM conversations."""
    user = MagicMock()
    user.id = 123456789
    user.name = "TestUser"
    user.send = AsyncMock()
    return user
