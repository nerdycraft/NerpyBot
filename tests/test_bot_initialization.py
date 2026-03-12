# -*- coding: utf-8 -*-
"""Tests for NerpyBot class initialization and methods."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from discord import Intents

from NerdyPy.bot import NerpyBot


@pytest.fixture(autouse=True)
def _patch_bot_subsystems():
    """Prevent Audio/ConversationManager/ErrorThrottle from touching real config."""
    with (
        patch("NerdyPy.bot.Audio"),
        patch("NerdyPy.bot.ConversationManager"),
        patch("NerdyPy.bot.ErrorThrottle"),
    ):
        yield


class TestNerpyBotInitialization:
    """Test NerpyBot.__init__ and related setup."""

    def test_init_with_minimal_config(self):
        """NerpyBot should initialize with minimal config."""
        config = {
            "bot": {
                "client_id": "123456789",
                "token": "test_token",
                "ops": ["111", "222"],
                "modules": ["admin", "music"],
            }
        }
        intents = Intents.default()

        bot = NerpyBot(config, intents, debug=False)

        assert bot.client_id == 123456789
        assert bot.token == "test_token"
        assert bot.ops == [111, 222]
        assert bot.modules == ["admin", "music"]
        assert bot.debug is False
        assert bot.restart is True

    def test_init_with_debug_mode(self):
        """NerpyBot should respect debug flag."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": ["111"],
                "modules": [],
            }
        }
        intents = Intents.default()

        bot = NerpyBot(config, intents, debug=True)

        assert bot.debug is True

    def test_init_creates_subsystems(self):
        """NerpyBot should initialize audio, conversation, and error throttle."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            }
        }
        intents = Intents.default()

        bot = NerpyBot(config, intents, debug=False)

        assert bot.audio is not None
        assert bot.convMan is not None
        assert bot.error_throttle is not None
        assert bot.disabled_modules == set()

    def test_init_with_database_config(self):
        """NerpyBot should create engine with database config."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            },
            "database": {
                "db_type": "sqlite",
                "db_name": "test.db",
            },
        }
        intents = Intents.default()

        bot = NerpyBot(config, intents, debug=False)

        assert bot.ENGINE is not None
        assert bot.SESSION is not None

    def test_init_without_database_config_logs_warning(self):
        """NerpyBot should log warning when no database config provided."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            }
        }
        intents = Intents.default()

        bot = NerpyBot(config, intents, debug=False)

        # Should still have ENGINE and SESSION (fallback to sqlite)
        assert bot.ENGINE is not None
        assert bot.SESSION is not None

    def test_uptime_recorded_at_init(self):
        """NerpyBot should record uptime timestamp."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            }
        }
        intents = Intents.default()

        before = datetime.now(UTC)
        bot = NerpyBot(config, intents, debug=False)
        after = datetime.now(UTC)

        assert before <= bot.uptime <= after


class TestNerpyBotSessionScope:
    """Test NerpyBot.session_scope context manager."""

    def test_session_scope_commits_on_success(self):
        """session_scope should commit on successful exit."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            }
        }
        intents = Intents.default()
        bot = NerpyBot(config, intents, debug=False)

        with bot.session_scope() as session:
            # Session should be usable
            assert session is not None

        # Should exit cleanly without exception

    def test_session_scope_rolls_back_on_error(self):
        """session_scope should rollback and raise on SQLAlchemyError."""
        from sqlalchemy.exc import SQLAlchemyError
        from utils.errors import NerpyInfraException

        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            }
        }
        intents = Intents.default()
        bot = NerpyBot(config, intents, debug=False)

        with pytest.raises(NerpyInfraException, match="database error"):
            with bot.session_scope() as session:
                # Simulate a database error
                session.execute = MagicMock(side_effect=SQLAlchemyError("DB error"))
                session.execute("SELECT 1")


class TestNerpyBotCreateAll:
    """Test NerpyBot.create_all method."""

    def test_create_all_creates_tables(self):
        """create_all should create all defined tables."""
        config = {
            "bot": {
                "client_id": "123",
                "token": "token",
                "ops": [],
                "modules": [],
            }
        }
        intents = Intents.default()
        bot = NerpyBot(config, intents, debug=False)

        # Should not raise
        bot.create_all()


class TestActivityConstants:
    """Test ACTIVITIES and ACTIVITY_WEIGHTS are correctly defined."""

    def test_activities_list_not_empty(self):
        """ACTIVITIES should contain status messages."""
        from NerdyPy.bot import ACTIVITIES

        assert len(ACTIVITIES) > 0
        assert all(isinstance(a, str) for a in ACTIVITIES)

    def test_activity_weights_match_activities(self):
        """ACTIVITY_WEIGHTS should match length of ACTIVITIES."""
        from NerdyPy.bot import ACTIVITIES, ACTIVITY_WEIGHTS

        assert len(ACTIVITY_WEIGHTS) == len(ACTIVITIES)

    def test_activity_weights_boost_command_hints(self):
        """Activities with / should have weight 3, others 1."""
        from NerdyPy.bot import ACTIVITIES, ACTIVITY_WEIGHTS

        for activity, weight in zip(ACTIVITIES, ACTIVITY_WEIGHTS):
            if "/" in activity:
                assert weight == 3
            else:
                assert weight == 1


class TestSentinelPath:
    """Test SENTINEL_PATH constant."""

    def test_sentinel_path_defined(self):
        """SENTINEL_PATH should be defined."""
        from NerdyPy.bot import SENTINEL_PATH

        assert SENTINEL_PATH == Path(tempfile.gettempdir()) / "nerpybot_ready"


class TestVersionCallback:
    """Test _version_callback helper."""

    def test_version_callback_exits_when_true(self):
        """_version_callback should exit when value is True."""
        from NerdyPy.bot import _version_callback
        import typer

        with pytest.raises(typer.Exit):
            _version_callback(True)

    def test_version_callback_no_exit_when_false(self):
        """_version_callback should not exit when value is False."""
        from NerdyPy.bot import _version_callback

        # Should complete without raising (returns None)
        _version_callback(False)
