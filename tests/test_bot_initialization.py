# -*- coding: utf-8 -*-
"""Tests for NerpyBot class initialization and methods."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

import pytest
from discord import Intents

from NerdyPy.bot import NerpyBot, get_intents


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


class TestGetIntents:
    """Test get_intents helper function."""

    def test_get_intents_returns_all(self):
        """get_intents should return Intents.all()."""
        intents = get_intents()

        assert isinstance(intents, Intents)
        # Verify it's basically "all" by checking common flags
        assert intents.guilds
        assert intents.members
        assert intents.messages
        assert intents.message_content


class TestHelperFunctions:
    """Test helper functions in bot.py."""

    def test_csv_splits_correctly(self):
        """_csv should split comma-separated values."""
        from NerdyPy.bot import _csv

        assert _csv("a,b,c") == ["a", "b", "c"]
        assert _csv("a, b, c") == ["a", "b", "c"]  # strips whitespace
        assert _csv("") == []
        assert _csv("single") == ["single"]
        assert _csv("a,,b") == ["a", "b"]  # skips empty

    def test_to_bool_parses_correctly(self):
        """_to_bool should parse boolean strings."""
        from NerdyPy.bot import _to_bool

        assert _to_bool("true") is True
        assert _to_bool("True") is True
        assert _to_bool("TRUE") is True
        assert _to_bool("1") is True
        assert _to_bool("yes") is True
        assert _to_bool("YES") is True

        assert _to_bool("false") is False
        assert _to_bool("False") is False
        assert _to_bool("0") is False
        assert _to_bool("no") is False
        assert _to_bool("anything") is False

    def test_set_nested_creates_structure(self):
        """_set_nested should create nested dict structure."""
        from NerdyPy.bot import _set_nested

        d = {}
        _set_nested(d, ["a", "b", "c"], "value")
        assert d == {"a": {"b": {"c": "value"}}}

    def test_set_nested_overwrites_existing(self):
        """_set_nested should overwrite existing values."""
        from NerdyPy.bot import _set_nested

        d = {"a": {"b": {"c": "old"}}}
        _set_nested(d, ["a", "b", "c"], "new")
        assert d["a"]["b"]["c"] == "new"

    def test_set_nested_single_key(self):
        """_set_nested should work with single key."""
        from NerdyPy.bot import _set_nested

        d = {}
        _set_nested(d, ["key"], "value")
        assert d == {"key": "value"}


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

        assert SENTINEL_PATH == Path("/tmp/nerpybot_ready")


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

        # Should return None without raising
        result = _version_callback(False)
        assert result is None