"""Tests for the Twitch notification slash command Cog."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


@pytest.fixture(autouse=True)
def _load_locale_strings():
    from utils.strings import load_strings

    load_strings()


def _make_interaction(guild_id: int = 111, user_id: int = 999):
    inter = MagicMock()
    inter.guild = MagicMock()
    inter.guild.id = guild_id
    inter.guild_id = guild_id
    inter.user = MagicMock()
    inter.user.id = user_id
    inter.response = MagicMock()
    inter.response.send_message = AsyncMock()
    inter.response.is_done = MagicMock(return_value=False)
    inter.followup = MagicMock()
    inter.followup.send = AsyncMock()
    return inter


class TestTwitchCog:
    @pytest.mark.asyncio
    async def test_setup_skips_when_no_twitch_config(self, mock_bot):
        mock_bot.config = {}
        from modules.twitch import setup

        await setup(mock_bot)
        mock_bot.add_cog.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_command_inserts_row(self, mock_bot, db_session):
        mock_bot.config = {"twitch": {}}
        from modules.twitch import TwitchNotificationsCog

        cog = TwitchNotificationsCog.__new__(TwitchNotificationsCog)
        cog.bot = mock_bot

        inter = _make_interaction()
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = 222

        await TwitchNotificationsCog.add.callback(
            cog, inter, streamer="shroud", channel=mock_channel, message=None, notify_offline=False
        )

        from models.twitch import TwitchNotifications

        with mock_bot.session_scope() as session:
            rows = TwitchNotifications.get_all_by_guild(111, session)
        assert len(rows) == 1
        assert rows[0].Streamer == "shroud"

    @pytest.mark.asyncio
    async def test_list_empty(self, mock_bot, db_session):
        mock_bot.config = {"twitch": {}}
        from modules.twitch import TwitchNotificationsCog

        cog = TwitchNotificationsCog.__new__(TwitchNotificationsCog)
        cog.bot = mock_bot

        inter = _make_interaction()
        await TwitchNotificationsCog.list.callback(cog, inter)
        inter.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_not_found(self, mock_bot, db_session):
        mock_bot.config = {"twitch": {}}
        from modules.twitch import TwitchNotificationsCog

        cog = TwitchNotificationsCog.__new__(TwitchNotificationsCog)
        cog.bot = mock_bot

        inter = _make_interaction()
        await TwitchNotificationsCog.remove.callback(cog, inter, config_id=9999)
        inter.response.send_message.assert_called_once()
