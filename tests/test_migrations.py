"""Tests for run_migrations() in bot.py."""

from unittest.mock import MagicMock, patch

import pytest

from NerdyPy.bot import run_migrations


def test_run_migrations_calls_alembic_upgrade():
    """run_migrations() should call alembic.command.upgrade with 'head'."""
    mock_config = MagicMock()

    with (
        patch("NerdyPy.bot.Config", return_value=mock_config) as mock_cfg_cls,
        patch("NerdyPy.bot.alembic_command") as mock_cmd,
    ):
        run_migrations()

        # Config constructed with a Path pointing to alembic.ini
        called_path = mock_cfg_cls.call_args[0][0]
        assert called_path.name == "alembic.ini"
        # upgrade("head") was called with the config object
        mock_cmd.upgrade.assert_called_once_with(mock_config, "head")


def test_run_migrations_propagates_exceptions():
    """Migration failures must propagate — not be swallowed."""
    with (
        patch("NerdyPy.bot.Config"),
        patch("NerdyPy.bot.alembic_command") as mock_cmd,
    ):
        mock_cmd.upgrade.side_effect = RuntimeError("DB unreachable")

        with pytest.raises(RuntimeError, match="DB unreachable"):
            run_migrations()


@pytest.mark.asyncio
async def test_on_ready_writes_sentinel(tmp_path):
    """on_ready() must write the readiness sentinel file."""
    sentinel = tmp_path / "nerpybot_ready"

    # Call on_ready as an unbound method, passing a heavily mocked 'self'.
    # MagicMock handles all attribute access (session_scope, guilds, config, etc.)
    # transparently. We only need to assert the sentinel was written.
    mock_self = MagicMock()
    mock_self.guilds = []
    mock_self.modules = []
    mock_self.config = {}
    mock_self.log = MagicMock()
    # Prevent on_ready from trying to create asyncio tasks (needs a running loop)
    mock_self._activity_task.done.return_value = False
    mock_self._valkey_task.done.return_value = False
    # session_scope must be a context manager
    mock_self.session_scope.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_self.session_scope.return_value.__exit__ = MagicMock(return_value=False)

    with patch("NerdyPy.bot.SENTINEL_PATH", sentinel):
        from NerdyPy.bot import NerpyBot

        await NerpyBot.on_ready(mock_self)

    assert sentinel.exists(), "on_ready must write /tmp/nerpybot_ready"


def test_run_migrations_locates_alembic_ini():
    """run_migrations() should locate alembic.ini relative to bot.py."""
    with (
        patch("NerdyPy.bot.Config") as mock_cfg_cls,
        patch("NerdyPy.bot.alembic_command") as mock_cmd,
    ):
        run_migrations()

        # Verify the alembic.ini path is constructed correctly
        called_path = mock_cfg_cls.call_args[0][0]
        assert called_path.name == "alembic.ini"
        assert called_path.is_absolute()


def test_run_migrations_upgrades_to_head():
    """run_migrations() should always upgrade to 'head' revision."""
    mock_config = MagicMock()

    with (
        patch("NerdyPy.bot.Config", return_value=mock_config),
        patch("NerdyPy.bot.alembic_command") as mock_cmd,
    ):
        run_migrations()

        # Second argument should be "head"
        assert mock_cmd.upgrade.call_args[0][1] == "head"


def test_run_migrations_with_different_db_errors():
    """run_migrations() should propagate various database errors."""
    from sqlalchemy.exc import OperationalError

    with (
        patch("NerdyPy.bot.Config"),
        patch("NerdyPy.bot.alembic_command") as mock_cmd,
    ):
        mock_cmd.upgrade.side_effect = OperationalError("Connection failed", None, None)

        with pytest.raises(OperationalError, match="Connection failed"):
            run_migrations()