"""Comprehensive tests for bot.py functions and NerpyBot class."""

from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from NerdyPy.bot import get_intents
from NerdyPy.utils.config import _csv, _to_bool, _set_nested
from NerdyPy.utils.valkey import valkey_listener_loop as _valkey_listener_loop


@pytest.fixture(autouse=True)
def _patch_bot_subsystems():
    """Prevent Audio/ConversationManager/ErrorThrottle from touching real config."""
    with (
        patch("NerdyPy.bot.Audio"),
        patch("NerdyPy.bot.ConversationManager"),
        patch("NerdyPy.bot.ErrorThrottle"),
    ):
        yield


def _mock_session_scope(mock_self) -> None:
    """Configure mock_self.session_scope to behave as a no-op context manager."""
    mock_self.session_scope.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_self.session_scope.return_value.__exit__ = MagicMock(return_value=False)


class TestHelperFunctions:
    """Test helper functions in utils/config.py."""

    def test_csv_splits_comma_separated_values(self):
        """_csv() should split comma-separated string into list."""
        assert _csv("one,two,three") == ["one", "two", "three"]

    def test_csv_strips_whitespace(self):
        """_csv() should strip whitespace from values."""
        assert _csv("one, two , three") == ["one", "two", "three"]

    def test_csv_removes_empty_strings(self):
        """_csv() should filter out empty strings."""
        assert _csv("one,,three,") == ["one", "three"]

    def test_csv_empty_string(self):
        """_csv() should return empty list for empty string."""
        assert _csv("") == []

    def test_csv_whitespace_only(self):
        """_csv() should return empty list for whitespace-only string."""
        assert _csv("  ,  ,  ") == []

    def test_to_bool_true_values(self):
        """_to_bool() should return True for true-like strings."""
        assert _to_bool("1") is True
        assert _to_bool("true") is True
        assert _to_bool("True") is True
        assert _to_bool("TRUE") is True
        assert _to_bool("yes") is True
        assert _to_bool("YES") is True
        assert _to_bool("Yes") is True

    def test_to_bool_false_values(self):
        """_to_bool() should return False for other strings."""
        assert _to_bool("0") is False
        assert _to_bool("false") is False
        assert _to_bool("no") is False
        assert _to_bool("anything") is False
        assert _to_bool("") is False

    def test_set_nested_single_level(self):
        """_set_nested() should set value at single level."""
        d = {}
        _set_nested(d, ["key"], "value")
        assert d == {"key": "value"}

    def test_set_nested_multiple_levels(self):
        """_set_nested() should create nested dicts."""
        d = {}
        _set_nested(d, ["level1", "level2", "level3"], "value")
        assert d == {"level1": {"level2": {"level3": "value"}}}

    def test_set_nested_preserves_existing_keys(self):
        """_set_nested() should preserve existing keys."""
        d = {"level1": {"existing": "value"}}
        _set_nested(d, ["level1", "level2"], "new")
        assert d == {"level1": {"existing": "value", "level2": "new"}}

    def test_set_nested_overwrites_value(self):
        """_set_nested() should overwrite existing value."""
        d = {"level1": {"level2": "old"}}
        _set_nested(d, ["level1", "level2"], "new")
        assert d == {"level1": {"level2": "new"}}


class TestGetIntents:
    """Test get_intents() function."""

    def test_get_intents_returns_all_intents(self):
        """get_intents() should return Intents.all()."""
        intents = get_intents()
        assert intents is not None
        # Verify it's an Intents object with all enabled
        assert intents.guilds is True
        assert intents.members is True
        assert intents.messages is True
        assert intents.message_content is True
        assert intents.reactions is True


class TestNerpyBotBuildConnectionString:
    """Test NerpyBot.build_connection_string() method."""

    def test_sqlite_default_when_no_database(self):
        """Should return sqlite:///db.db when no database config."""
        from NerdyPy.bot import NerpyBot

        config = {}
        result = NerpyBot.build_connection_string(config)
        assert result == "sqlite:///db.db"

    def test_sqlite_connection_string(self):
        """Should build SQLite connection string."""
        from NerdyPy.bot import NerpyBot

        config = {"database": {"db_type": "sqlite", "db_name": "/data/mydb.db"}}
        result = NerpyBot.build_connection_string(config)
        assert result == "sqlite:////data/mydb.db"

    def test_postgresql_connection_string(self):
        """Should build PostgreSQL connection string with psycopg."""
        from NerdyPy.bot import NerpyBot

        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "admin",
                "db_password": "secret",
                "db_host": "localhost",
                "db_port": "5432",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg://admin:secret@localhost:5432/nerpybot"

    def test_postgresql_without_port(self):
        """Should build PostgreSQL connection string without port."""
        from NerdyPy.bot import NerpyBot

        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "admin",
                "db_password": "secret",
                "db_host": "localhost",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg://admin:secret@localhost/nerpybot"

    def test_postgresql_without_password(self):
        """Should build PostgreSQL connection string without password."""
        from NerdyPy.bot import NerpyBot

        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "admin",
                "db_host": "localhost",
                "db_port": "5432",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg://admin@localhost:5432/nerpybot"

    def test_postgresql_minimal(self):
        """Should build minimal PostgreSQL connection string."""
        from NerdyPy.bot import NerpyBot

        config = {"database": {"db_type": "postgresql", "db_name": "nerpybot"}}
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg:///nerpybot"

    def test_postgresql_empty_password(self):
        """Should handle empty password string."""
        from NerdyPy.bot import NerpyBot

        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "admin",
                "db_password": "",
                "db_host": "localhost",
            }
        }
        result = NerpyBot.build_connection_string(config)
        # Empty password should not add colon
        assert result == "postgresql+psycopg://admin@localhost/nerpybot"


class TestNerpyBotInit:
    """Test NerpyBot.__init__() method."""

    def test_nerpybot_init_parses_config(self):
        """NerpyBot.__init__() should parse config correctly."""
        from NerdyPy.bot import NerpyBot
        from discord import Intents

        config = {
            "bot": {"token": "test_token", "client_id": "12345", "ops": ["111", "222"], "modules": ["admin", "music"]}
        }

        with (
            patch("NerdyPy.bot.create_engine"),
            patch("NerdyPy.bot.sessionmaker"),
        ):
            bot = NerpyBot(config, Intents.all(), debug=False)

            assert bot.client_id == 12345
            assert bot.token == "test_token"
            assert bot.ops == [111, 222]
            assert bot.modules == ["admin", "music"]
            assert bot.debug is False
            assert bot.restart is True
            assert bot.disabled_modules == set()

    def test_nerpybot_init_handles_missing_database_config(self):
        """NerpyBot.__init__() should warn when database config missing."""
        from NerdyPy.bot import NerpyBot
        from discord import Intents

        config = {"bot": {"token": "test_token", "client_id": "12345", "ops": ["111"], "modules": []}}

        with (
            patch("NerdyPy.bot.create_engine"),
            patch("NerdyPy.bot.sessionmaker"),
            patch("NerdyPy.bot.logging.get_logger") as mock_logger,
        ):
            mock_log = MagicMock()
            mock_logger.return_value = mock_log

            NerpyBot(config, Intents.all(), debug=False)

            # Should log warning about missing database config
            mock_log.warning.assert_called_once()
            warning_msg = str(mock_log.warning.call_args[0][0])
            assert "No Database specified" in warning_msg

    def test_nerpybot_init_debug_mode(self):
        """NerpyBot.__init__() should set debug flag."""
        from NerdyPy.bot import NerpyBot
        from discord import Intents

        config = {"bot": {"token": "test_token", "client_id": "12345", "ops": ["111"], "modules": []}}

        with (
            patch("NerdyPy.bot.create_engine"),
            patch("NerdyPy.bot.sessionmaker"),
        ):
            bot = NerpyBot(config, Intents.all(), debug=True)
            assert bot.debug is True


class TestNerpyBotSessionScope:
    """Test NerpyBot.session_scope() context manager."""

    def test_nerpybot_session_scope_commits_on_success(self, db_engine):
        """NerpyBot.session_scope() should commit on success."""
        from NerdyPy.bot import NerpyBot
        from discord import Intents
        from models.guild import BotGuild

        config = {"bot": {"token": "test_token", "client_id": "12345", "ops": ["111"], "modules": []}}

        bot = NerpyBot(config, Intents.all(), debug=False)
        bot.ENGINE = db_engine
        from sqlalchemy.orm import sessionmaker

        bot.SESSION = sessionmaker(bind=db_engine, expire_on_commit=False)

        with bot.session_scope() as session:
            BotGuild.add(12345, session)

        # After exiting context, changes should be committed
        with bot.session_scope() as session:
            guild = session.query(BotGuild).filter_by(GuildId=12345).first()
            assert guild is not None

    def test_nerpybot_session_scope_rolls_back_on_error(self, db_engine):
        """NerpyBot.session_scope() should rollback on exception."""
        from NerdyPy.bot import NerpyBot
        from discord import Intents
        from utils.errors import NerpyInfraException
        from sqlalchemy.exc import SQLAlchemyError

        config = {"bot": {"token": "test_token", "client_id": "12345", "ops": ["111"], "modules": []}}

        bot = NerpyBot(config, Intents.all(), debug=False)
        bot.ENGINE = db_engine
        from sqlalchemy.orm import sessionmaker

        bot.SESSION = sessionmaker(bind=db_engine, expire_on_commit=False)

        # Raising SQLAlchemyError inside session_scope should rollback and re-raise as NerpyInfraException
        with pytest.raises(NerpyInfraException):
            with bot.session_scope():
                raise SQLAlchemyError("forced error")


class TestOnReady:
    """Test NerpyBot.on_ready() method."""

    @pytest.mark.asyncio
    async def test_on_ready_starts_valkey_listener(self, tmp_path):
        """on_ready() should start Valkey listener if configured."""
        sentinel = tmp_path / "nerpybot_ready"

        mock_self = MagicMock()
        mock_self.guilds = []
        mock_self.modules = []
        mock_self.config = {"web": {"valkey_url": "valkey://localhost:6379"}}
        mock_self.log = MagicMock()
        mock_self._activity_task.done.return_value = True
        # remove auto-created MagicMock attribute so hasattr() returns False, simulating first run
        delattr(mock_self, "_valkey_task")
        _mock_session_scope(mock_self)

        def _fake_create_task(coro):
            if hasattr(coro, "close"):
                coro.close()  # prevent unawaited-coroutine warning
            return MagicMock()

        with (
            patch("NerdyPy.bot.SENTINEL_PATH", sentinel),
            patch("NerdyPy.bot.create_task", side_effect=_fake_create_task) as mock_create_task,
        ):
            from NerdyPy.bot import NerpyBot

            await NerpyBot.on_ready(mock_self)

            # Should create both activity loop and Valkey listener tasks
            assert mock_create_task.call_count == 2

    @pytest.mark.asyncio
    async def test_on_ready_logs_missing_permissions(self, tmp_path):
        """on_ready() should log warnings for missing permissions."""
        sentinel = tmp_path / "nerpybot_ready"

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_guild.name = "Test Guild"

        mock_self = MagicMock()
        mock_self.guilds = [mock_guild]
        mock_self.modules = ["music", "wow"]
        mock_self.config = {}
        mock_self.log = MagicMock()
        mock_self.client_id = 111222333
        mock_self._activity_task.done.return_value = True
        delattr(mock_self, "_valkey_task")
        _mock_session_scope(mock_self)

        with (
            patch("NerdyPy.bot.SENTINEL_PATH", sentinel),
            patch("NerdyPy.bot.create_task"),
            patch("NerdyPy.bot.required_permissions_for") as mock_required,
            patch("NerdyPy.bot.check_guild_permissions") as mock_check,
            patch("NerdyPy.bot.build_permissions_embed"),
        ):
            mock_required.return_value = {"connect": True, "speak": True}
            mock_check.return_value = ["connect"]

            from NerdyPy.bot import NerpyBot

            await NerpyBot.on_ready(mock_self)

            # Should log warning about missing permissions
            mock_self.log.warning.assert_called()
            calls = [str(call[0][0]) for call in mock_self.log.warning.call_args_list]
            assert any("Test Guild" in msg and "missing permissions" in msg for msg in calls)

    @pytest.mark.asyncio
    async def test_on_ready_handles_valkey_config_missing(self, tmp_path):
        """on_ready() should not start Valkey listener if config missing."""
        from NerdyPy.bot import NerpyBot

        sentinel = tmp_path / "nerpybot_ready"

        mock_self = MagicMock()
        mock_self.guilds = []
        mock_self.modules = []
        mock_self.config = {}  # No web.valkey_url
        mock_self.log = MagicMock()
        mock_self._activity_task.done.return_value = True
        delattr(mock_self, "_valkey_task")
        _mock_session_scope(mock_self)

        with (
            patch("NerdyPy.bot.SENTINEL_PATH", sentinel),
            patch("NerdyPy.bot.create_task") as mock_create_task,
        ):
            await NerpyBot.on_ready(mock_self)

            # Should only create activity loop task, not Valkey listener
            assert mock_create_task.call_count == 1


class TestValkeyListenerLoop:
    """Test _valkey_listener_loop() function."""

    @pytest.mark.asyncio
    async def test_valkey_listener_subscribes_to_channel(self):
        """_valkey_listener_loop() should subscribe to nerpybot:cmd channel."""
        mock_bot = MagicMock()
        # False: enter outer loop; True: exit inner loop; True: exit outer loop
        mock_bot.is_closed = MagicMock(side_effect=[False, True, True])
        mock_bot.log = MagicMock()

        mock_client = MagicMock()
        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = MagicMock()
        mock_pubsub.unsubscribe = MagicMock()
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_client.close = MagicMock()

        with (
            patch("NerdyPy.utils.valkey.to_thread", new_callable=AsyncMock),
        ):
            import valkey as valkey_lib

            with patch.object(valkey_lib, "from_url", return_value=mock_client):
                await _valkey_listener_loop(mock_bot, "valkey://localhost:6379")

                # Should have subscribed to channel
                mock_pubsub.subscribe.assert_called_once_with("nerpybot:cmd")

    @pytest.mark.asyncio
    async def test_valkey_listener_handles_cancelled_error(self):
        """_valkey_listener_loop() should exit gracefully on CancelledError."""
        from asyncio import CancelledError

        mock_bot = MagicMock()
        mock_bot.is_closed = MagicMock(side_effect=CancelledError)
        mock_bot.log = MagicMock()

        with patch("NerdyPy.utils.valkey.to_thread", new_callable=AsyncMock):
            import valkey as valkey_lib

            with patch.object(valkey_lib, "from_url", return_value=MagicMock()):
                await _valkey_listener_loop(mock_bot, "valkey://localhost:6379")
                # Should exit without raising

    @pytest.mark.asyncio
    async def test_valkey_listener_logs_errors(self):
        """_valkey_listener_loop() should log errors."""
        mock_bot = MagicMock()
        mock_bot.log = MagicMock()
        # False: enter outer loop; True: exit after error + sleep
        mock_bot.is_closed = MagicMock(side_effect=[False, True])

        with (
            patch("NerdyPy.utils.valkey.sleep", new_callable=AsyncMock),
        ):
            import valkey as valkey_lib

            with patch.object(valkey_lib, "from_url", side_effect=Exception("Connection failed")):
                await _valkey_listener_loop(mock_bot, "valkey://localhost:6379")

                # Should log the error
                mock_bot.log.error.assert_called()


class TestVersionCallback:
    """Test _version_callback() function."""

    def test_version_callback_prints_version_and_exits(self):
        """_version_callback() should print version and exit when True."""
        from NerdyPy.bot import _version_callback
        import typer

        with (
            patch("NerdyPy.bot.typer.echo") as mock_echo,
            patch("NerdyPy.bot.pkg_version", return_value="1.2.3"),
        ):
            with pytest.raises(typer.Exit):
                _version_callback(True)

            mock_echo.assert_called_once()
            assert "1.2.3" in str(mock_echo.call_args[0][0])

    def test_version_callback_no_op_when_false(self):
        """_version_callback() should do nothing when False."""
        from NerdyPy.bot import _version_callback

        _version_callback(False)


class TestActivityLoop:
    """Test _activity_loop() method."""

    @pytest.mark.asyncio
    async def test_activity_loop_changes_presence(self):
        """_activity_loop() should change bot presence."""
        from NerdyPy.bot import NerpyBot

        mock_self = MagicMock()
        mock_self.is_closed = MagicMock(side_effect=[False, True])  # Run once then exit
        mock_self.change_presence = AsyncMock()

        with patch("NerdyPy.bot.sleep", new_callable=AsyncMock):
            await NerpyBot._activity_loop(mock_self)

            # Should have changed presence
            mock_self.change_presence.assert_called_once()

    @pytest.mark.asyncio
    async def test_activity_loop_handles_cancelled_error(self):
        """_activity_loop() should exit gracefully on CancelledError."""
        from NerdyPy.bot import NerpyBot
        from asyncio import CancelledError

        mock_self = MagicMock()
        mock_self.is_closed = MagicMock(side_effect=CancelledError)

        await NerpyBot._activity_loop(mock_self)
        # Should exit without raising

    @pytest.mark.asyncio
    async def test_activity_loop_logs_errors(self):
        """_activity_loop() should log errors."""
        from NerdyPy.bot import NerpyBot

        mock_self = MagicMock()
        mock_self.is_closed = MagicMock(side_effect=Exception("Test error"))
        mock_self.log = MagicMock()

        await NerpyBot._activity_loop(mock_self)

        # Should log the error
        mock_self.log.error.assert_called()


class TestGlobalInteractionCheck:
    """Test _global_interaction_check() method."""

    @pytest.mark.asyncio
    async def test_global_interaction_check_allows_non_disabled_modules(self):
        """_global_interaction_check() should allow commands from enabled modules."""
        from NerdyPy.bot import NerpyBot

        mock_interaction = MagicMock()
        mock_command = MagicMock()
        mock_cog = MagicMock()
        mock_cog.__module__ = "modules.music"
        mock_command.binding = mock_cog
        mock_interaction.command = mock_command

        mock_self = MagicMock()
        mock_self.disabled_modules = set()

        result = await NerpyBot._global_interaction_check(mock_self, mock_interaction)
        assert result is True

    @pytest.mark.asyncio
    async def test_global_interaction_check_blocks_disabled_modules(self):
        """_global_interaction_check() should block commands from disabled modules."""
        from NerdyPy.bot import NerpyBot
        from utils.errors import SilentCheckFailure

        mock_interaction = MagicMock()
        mock_interaction.guild_id = 12345
        mock_interaction.response.is_done = MagicMock(return_value=False)
        mock_interaction.response.send_message = AsyncMock()
        mock_command = MagicMock()
        mock_cog = MagicMock()
        mock_cog.__module__ = "modules.music"
        type(mock_cog).__module__ = "modules.music"
        mock_command.binding = mock_cog
        mock_interaction.command = mock_command

        mock_self = MagicMock()
        mock_self.disabled_modules = {"music"}
        mock_self.get_localized_string.return_value = "Module disabled"

        with pytest.raises(SilentCheckFailure):
            await NerpyBot._global_interaction_check(mock_self, mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        mock_self.get_localized_string.assert_called_once()
        assert mock_self.get_localized_string.call_args.args[0] == mock_interaction.guild_id


class TestRunMigrations:
    """Test run_migrations() logging and error handling."""

    def test_run_migrations_logs_start_and_complete(self, tmp_path):
        """run_migrations() should log start and complete messages on success."""
        from NerdyPy.bot import run_migrations

        (tmp_path / "alembic.ini").touch()

        with (
            patch("NerdyPy.bot.Path") as mock_path_cls,
            patch("NerdyPy.bot.alembic_command.upgrade"),
            patch("NerdyPy.bot.Config"),
            patch("NerdyPy.bot.logging.get_logger") as mock_get_logger,
        ):
            mock_log = MagicMock()
            mock_get_logger.return_value = mock_log

            mock_resolve = MagicMock()
            mock_resolve.parents = [tmp_path]
            mock_path_cls.return_value.resolve.return_value = mock_resolve

            run_migrations()

        calls = [str(c[0][0]) for c in mock_log.info.call_args_list]
        assert any("Running database migrations" in msg for msg in calls)
        assert any("complete" in msg.lower() for msg in calls)

    def test_run_migrations_logs_error_and_reraises(self, tmp_path):
        """run_migrations() should log the error and re-raise on failure."""
        from NerdyPy.bot import run_migrations

        (tmp_path / "alembic.ini").touch()

        with (
            patch("NerdyPy.bot.Path") as mock_path_cls,
            patch("NerdyPy.bot.alembic_command.upgrade", side_effect=RuntimeError("migration failed")),
            patch("NerdyPy.bot.Config"),
            patch("NerdyPy.bot.logging.get_logger") as mock_get_logger,
        ):
            mock_log = MagicMock()
            mock_get_logger.return_value = mock_log

            mock_resolve = MagicMock()
            mock_resolve.parents = [tmp_path]
            mock_path_cls.return_value.resolve.return_value = mock_resolve

            with pytest.raises(RuntimeError, match="migration failed"):
                run_migrations()

        mock_log.error.assert_called_once()
        error_msg = str(mock_log.error.call_args[0][0])
        assert "migration failed" in error_msg

    def test_run_migrations_raises_when_ini_not_found(self, tmp_path):
        """run_migrations() should raise FileNotFoundError when alembic.ini is missing."""
        from NerdyPy.bot import run_migrations

        with patch("NerdyPy.bot.Path") as mock_path_cls:
            mock_resolve = MagicMock()
            # Empty parents list → for/else immediately hits the else branch
            mock_resolve.parents = []
            mock_path_cls.return_value.resolve.return_value = mock_resolve

            with pytest.raises(FileNotFoundError, match="alembic.ini not found"):
                run_migrations()
