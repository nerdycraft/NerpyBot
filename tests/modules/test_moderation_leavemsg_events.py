# -*- coding: utf-8 -*-
"""Tests for Moderation.on_member_remove event listener (leavemsg)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import NotFound, TextChannel

from models.leavemsg import LeaveMessage
from modules.moderation import Moderation
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    """Load locale YAML files before each test."""
    load_strings()


@pytest.fixture
def cog(mock_bot):
    # Use __new__ to avoid starting asyncio background loops outside an event loop
    c = Moderation.__new__(Moderation)
    c.bot = mock_bot
    return c


class TestOnMemberRemove:
    """Tests for the on_member_remove event listener."""

    @pytest.mark.asyncio
    async def test_sends_formatted_message_on_member_leave(self, cog, db_session):
        """A formatted message should be sent to the configured channel when a member leaves."""
        guild_id = 987654321
        channel_id = 111222333

        db_session.add(
            LeaveMessage(
                GuildId=guild_id,
                ChannelId=channel_id,
                Message="Goodbye {member}!",
                Enabled=True,
            )
        )
        db_session.commit()

        mock_channel = MagicMock(spec=TextChannel)
        mock_channel.id = channel_id
        mock_channel.send = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_channel = MagicMock(return_value=mock_channel)

        member = MagicMock()
        member.bot = False
        member.display_name = "Alice"
        member.name = "alice123"
        member.guild = mock_guild

        await cog.on_member_remove(member)

        mock_channel.send.assert_awaited_once()
        sent_text = mock_channel.send.call_args[0][0]
        assert "Alice" in sent_text
        assert "Goodbye" in sent_text

    @pytest.mark.asyncio
    async def test_disabled_config_does_not_send(self, cog, db_session):
        """When Enabled=False, no message should be sent."""
        guild_id = 987654321
        channel_id = 111222333

        db_session.add(
            LeaveMessage(
                GuildId=guild_id,
                ChannelId=channel_id,
                Message="Goodbye {member}!",
                Enabled=False,
            )
        )
        db_session.commit()

        mock_channel = MagicMock(spec=TextChannel)
        mock_channel.send = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_channel = MagicMock(return_value=mock_channel)

        member = MagicMock()
        member.bot = False
        member.display_name = "Alice"
        member.name = "alice123"
        member.guild = mock_guild

        await cog.on_member_remove(member)

        mock_channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_not_found_does_not_crash(self, cog, db_session):
        """When the channel no longer exists, on_member_remove should not raise."""
        guild_id = 987654321
        channel_id = 999999999

        db_session.add(
            LeaveMessage(
                GuildId=guild_id,
                ChannelId=channel_id,
                Message="Goodbye {member}!",
                Enabled=True,
            )
        )
        db_session.commit()

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_channel = MagicMock(return_value=None)
        mock_http_resp = MagicMock()
        mock_http_resp.status = 404
        mock_guild.fetch_channel = AsyncMock(side_effect=NotFound(mock_http_resp, "Unknown Channel"))

        member = MagicMock()
        member.bot = False
        member.display_name = "Alice"
        member.name = "alice123"
        member.guild = mock_guild

        # Should not raise
        await cog.on_member_remove(member)
