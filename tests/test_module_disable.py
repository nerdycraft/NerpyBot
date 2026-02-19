# -*- coding: utf-8 -*-
"""Tests for runtime module disable feature."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.errors import SilentCheckFailure


@pytest.fixture
def mock_bot_with_disable():
    """Minimal mock of NerpyBot with disabled_modules set."""
    bot = MagicMock()
    bot.disabled_modules = set()
    bot.log = MagicMock()
    return bot


@pytest.fixture
def mock_interaction_for_disable(mock_bot_with_disable):
    """Mock Interaction whose command lives in a cog."""
    interaction = MagicMock()
    interaction.client = mock_bot_with_disable

    # Build a command that belongs to a cog named "Wow" in module "modules.wow"
    cog = MagicMock()
    cog.qualified_name = "Wow"
    type(cog).__module__ = "modules.wow"

    command = MagicMock()
    command.binding = cog
    interaction.command = command

    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    return interaction


class TestGlobalInteractionCheck:
    """Tests for NerpyBot._global_interaction_check"""

    async def test_allows_command_when_module_not_disabled(self, mock_interaction_for_disable):
        from NerdyPy.NerdyPy import NerpyBot

        bot = mock_interaction_for_disable.client
        result = await NerpyBot._global_interaction_check(bot, mock_interaction_for_disable)
        assert result is True

    async def test_blocks_command_when_module_disabled(self, mock_interaction_for_disable):
        from NerdyPy.NerdyPy import NerpyBot

        bot = mock_interaction_for_disable.client
        bot.disabled_modules = {"wow"}

        with pytest.raises(SilentCheckFailure, match="disabled for maintenance"):
            await NerpyBot._global_interaction_check(bot, mock_interaction_for_disable)

        mock_interaction_for_disable.response.send_message.assert_awaited_once()
        msg = mock_interaction_for_disable.response.send_message.call_args[0][0]
        assert "wow" in msg
        assert "maintenance" in msg

    async def test_blocks_uses_followup_when_response_done(self, mock_interaction_for_disable):
        from NerdyPy.NerdyPy import NerpyBot

        bot = mock_interaction_for_disable.client
        bot.disabled_modules = {"wow"}
        mock_interaction_for_disable.response.is_done.return_value = True

        with pytest.raises(SilentCheckFailure):
            await NerpyBot._global_interaction_check(bot, mock_interaction_for_disable)

        mock_interaction_for_disable.followup.send.assert_awaited_once()

    async def test_allows_command_when_no_cog(self, mock_interaction_for_disable):
        """Commands without a cog binding (e.g. tree commands) should pass."""
        from NerdyPy.NerdyPy import NerpyBot

        bot = mock_interaction_for_disable.client
        bot.disabled_modules = {"wow"}
        mock_interaction_for_disable.command.binding = None

        result = await NerpyBot._global_interaction_check(bot, mock_interaction_for_disable)
        assert result is True

    async def test_allows_command_when_no_command(self, mock_interaction_for_disable):
        """Autocomplete interactions have no command -- should pass."""
        from NerdyPy.NerdyPy import NerpyBot

        bot = mock_interaction_for_disable.client
        bot.disabled_modules = {"wow"}
        mock_interaction_for_disable.command = None

        result = await NerpyBot._global_interaction_check(bot, mock_interaction_for_disable)
        assert result is True
