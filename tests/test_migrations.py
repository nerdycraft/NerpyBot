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

        # Config constructed with a path ending in alembic.ini
        called_path = mock_cfg_cls.call_args[0][0]
        assert called_path.endswith("alembic.ini")
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
