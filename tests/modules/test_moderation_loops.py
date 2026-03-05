# -*- coding: utf-8 -*-
"""Tests for Moderation background loops — autodeleter and autokicker."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.moderation import AutoDelete, AutoKicker
from modules.moderation import Moderation
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    """Load locale YAML files before each test."""
    load_strings()


@pytest.fixture
def moderation_cog(mock_bot):
    """Instantiate Moderation with both background loops fully stopped."""
    with patch.object(Moderation, "_autokicker_loop"), patch.object(Moderation, "_autodeleter_loop"):
        cog = Moderation.__new__(Moderation)
        cog.bot = mock_bot

        cog._autokicker_loop = MagicMock()
        cog._autokicker_loop.start = MagicMock()
        cog._autokicker_loop.cancel = MagicMock()

        cog._autodeleter_loop = MagicMock()
        cog._autodeleter_loop.start = MagicMock()
        cog._autodeleter_loop.cancel = MagicMock()

    return cog


def _async_iter(items):
    """Return an async iterable that yields the given items."""

    async def _gen():
        for item in items:
            yield item

    return _gen()


class TestAutoDeleteLoop:
    """Tests for the _autodeleter_loop body."""

    @pytest.mark.asyncio
    async def test_autodelete_deletes_old_messages(self, moderation_cog, db_session):
        """Only excess messages beyond KeepMessages should be deleted (oldest first)."""
        guild_id = 123
        channel_id = 456

        # KeepMessages=1 means keep the most recent message, delete the oldest
        db_session.add(
            AutoDelete(
                GuildId=guild_id,
                ChannelId=channel_id,
                DeleteOlderThan=3600,
                DeletePinnedMessage=True,
                KeepMessages=1,
                Enabled=True,
            )
        )
        db_session.commit()

        now = datetime.now(UTC)

        # oldest_first=True means old_msg is first in the list — it gets popped and deleted
        old_msg = MagicMock()
        old_msg.pinned = False
        old_msg.thread = None
        old_msg.delete = AsyncMock()
        old_msg.channel = MagicMock()
        old_msg.channel.name = "general"
        old_msg.author = MagicMock()
        old_msg.author.id = 999
        old_msg.created_at = now - timedelta(hours=3)

        # newer_msg is second; with KeepMessages=1 it is kept (list shrinks to <= message_limit)
        newer_msg = MagicMock()
        newer_msg.pinned = False
        newer_msg.thread = None
        newer_msg.delete = AsyncMock()
        newer_msg.channel = MagicMock()
        newer_msg.channel.name = "general"
        newer_msg.author = MagicMock()
        newer_msg.author.id = 998
        newer_msg.created_at = now - timedelta(hours=2)

        mock_channel = MagicMock()
        # channel.history(before=..., oldest_first=True) returns an async iterable
        mock_channel.history = MagicMock(return_value=_async_iter([old_msg, newer_msg]))

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_channel = MagicMock(return_value=mock_channel)

        moderation_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        # Invoke the loop body via the .coro attribute of the tasks.Loop descriptor
        await Moderation._autodeleter_loop.coro(moderation_cog)

        old_msg.delete.assert_awaited_once()
        newer_msg.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_autodelete_respects_pinned_flag(self, moderation_cog, db_session):
        """With DeletePinnedMessage=False, pinned messages must not be deleted."""
        guild_id = 123
        channel_id = 456

        db_session.add(
            AutoDelete(
                GuildId=guild_id,
                ChannelId=channel_id,
                DeleteOlderThan=3600,
                DeletePinnedMessage=False,
                KeepMessages=0,
                Enabled=True,
            )
        )
        db_session.commit()

        now = datetime.now(UTC)

        pinned_msg = MagicMock()
        pinned_msg.pinned = True
        pinned_msg.thread = None
        pinned_msg.delete = AsyncMock()
        pinned_msg.channel = MagicMock()
        pinned_msg.channel.name = "general"
        pinned_msg.author = MagicMock()
        pinned_msg.author.id = 999
        pinned_msg.created_at = now - timedelta(hours=2)

        normal_old_msg = MagicMock()
        normal_old_msg.pinned = False
        normal_old_msg.thread = None
        normal_old_msg.delete = AsyncMock()
        normal_old_msg.channel = MagicMock()
        normal_old_msg.channel.name = "general"
        normal_old_msg.author = MagicMock()
        normal_old_msg.author.id = 998
        normal_old_msg.created_at = now - timedelta(hours=3)

        mock_channel = MagicMock()
        mock_channel.history = MagicMock(return_value=_async_iter([pinned_msg, normal_old_msg]))

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_channel = MagicMock(return_value=mock_channel)

        moderation_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        await Moderation._autodeleter_loop.coro(moderation_cog)

        # Pinned message must NOT be deleted
        pinned_msg.delete.assert_not_called()
        # Normal old message MUST be deleted
        normal_old_msg.delete.assert_awaited_once()


class TestAutoKickerLoop:
    """Tests for the _autokicker_loop body."""

    @pytest.mark.asyncio
    async def test_autokicker_kicks_member_past_threshold(self, moderation_cog, db_session):
        """A member with no roles who joined beyond the KickAfter threshold should be kicked."""
        guild_id = 123
        kick_after_seconds = 7 * 24 * 3600  # 7 days

        db_session.add(
            AutoKicker(
                GuildId=guild_id,
                KickAfter=kick_after_seconds,
                Enabled=True,
                ReminderMessage=None,
            )
        )
        db_session.commit()

        # Member joined 8 days ago, has only @everyone (1 role entry)
        member = MagicMock()
        member.bot = False
        member.id = 777
        member.roles = [MagicMock()]  # just @everyone
        member.joined_at = datetime.now(UTC) - timedelta(days=8)
        member.kick = AsyncMock()
        member.send = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.members = [member]

        moderation_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        await Moderation._autokicker_loop.coro(moderation_cog)

        member.kick.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_autokicker_ignores_member_with_roles(self, moderation_cog, db_session):
        """A member with at least one real role (beyond @everyone) must not be kicked."""
        guild_id = 123
        kick_after_seconds = 7 * 24 * 3600  # 7 days

        db_session.add(
            AutoKicker(
                GuildId=guild_id,
                KickAfter=kick_after_seconds,
                Enabled=True,
                ReminderMessage=None,
            )
        )
        db_session.commit()

        # Member joined 8 days ago but HAS a real role (@everyone + 1 actual role = 2 entries)
        member = MagicMock()
        member.bot = False
        member.id = 777
        member.roles = [MagicMock(), MagicMock()]  # @everyone + one real role
        member.joined_at = datetime.now(UTC) - timedelta(days=8)
        member.kick = AsyncMock()
        member.send = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.members = [member]

        moderation_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        await Moderation._autokicker_loop.coro(moderation_cog)

        member.kick.assert_not_called()
