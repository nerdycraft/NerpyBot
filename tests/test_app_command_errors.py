# -*- coding: utf-8 -*-
"""Tests for NerpyBot._on_app_command_error — bot-level slash command error routing."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.app_commands import CommandInvokeError

from utils.errors import NerpyInfraException, NerpyUserException
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    """Load locale YAML files so localized messages resolve."""
    load_strings()


@pytest.fixture
def bot(db_session):
    """Minimal mock of NerpyBot sufficient for _on_app_command_error."""
    from utils.strings import get_string

    b = MagicMock()
    b.log = MagicMock()
    b.error_throttle = MagicMock()
    b.error_throttle.should_notify = MagicMock(return_value=True)
    b.config = {"notifications": {"error_recipients": []}}
    b.get_localized_string = lambda guild_id, key, **kwargs: get_string("en", key, **kwargs)

    @contextmanager
    def session_scope():
        yield db_session

    b.session_scope = session_scope
    return b


@pytest.fixture
def interaction():
    """Mock Interaction with is_done() returning False (response not yet sent)."""
    inter = MagicMock()
    inter.guild = MagicMock()
    inter.guild.id = 987654321
    inter.guild.name = "Test Guild"
    inter.guild_id = 987654321
    inter.user = MagicMock()
    inter.user.id = 123456789
    inter.user.__str__ = lambda _: "TestUser"
    inter.command = MagicMock()
    inter.command.qualified_name = "test"
    inter.response = MagicMock()
    inter.response.send_message = AsyncMock()
    inter.response.is_done = MagicMock(return_value=False)
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter


class TestOnAppCommandError:
    """Tests for NerpyBot._on_app_command_error."""

    @pytest.mark.asyncio
    async def test_nerpyuser_exception_sends_message_no_notify(self, bot, interaction):
        """NerpyUserException should send the error message and NOT call notify_error."""
        from NerdyPy.bot import NerpyBot

        original = NerpyUserException("user error")
        error = CommandInvokeError(MagicMock(), original)

        with patch("NerdyPy.bot.notify_error", new_callable=AsyncMock) as mock_notify:
            await NerpyBot._on_app_command_error(bot, interaction, error)

        # The error message should have been sent to the user
        calls = list(interaction.response.send_message.call_args_list) + list(interaction.followup.send.call_args_list)
        assert len(calls) == 1
        sent_text = str(calls[0])
        assert "user error" in sent_text

        # notify_error must NOT have been called
        mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_nerpyinfra_exception_sends_message_and_notifies(self, bot, interaction):
        """NerpyInfraException should send the error message AND call notify_error."""
        from NerdyPy.bot import NerpyBot

        original = NerpyInfraException("infra error")
        error = CommandInvokeError(MagicMock(), original)

        with patch("NerdyPy.bot.notify_error", new_callable=AsyncMock) as mock_notify:
            await NerpyBot._on_app_command_error(bot, interaction, error)

        # The error message should have been sent to the user
        calls = list(interaction.response.send_message.call_args_list) + list(interaction.followup.send.call_args_list)
        assert len(calls) == 1
        sent_text = str(calls[0])
        assert "infra error" in sent_text

        # notify_error MUST have been called
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_generic_exception_sends_generic_message_and_notifies(self, bot, interaction):
        """A plain Exception should send the generic error string and call notify_error."""
        from NerdyPy.bot import NerpyBot
        from utils.strings import get_string

        original = ValueError("boom")
        error = CommandInvokeError(MagicMock(), original)

        # is_done() returns False so the first send path is taken
        interaction.response.is_done.return_value = False

        with patch("NerdyPy.bot.notify_error", new_callable=AsyncMock) as mock_notify:
            await NerpyBot._on_app_command_error(bot, interaction, error)

        # The generic error string should have been sent
        expected_msg = get_string("en", "common.error_generic")
        interaction.response.send_message.assert_awaited_once_with(expected_msg, ephemeral=True)

        # notify_error MUST have been called
        mock_notify.assert_called_once()
