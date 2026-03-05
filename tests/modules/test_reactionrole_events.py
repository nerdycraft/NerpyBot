# -*- coding: utf-8 -*-
"""Tests for ReactionRole on_raw_reaction_add and on_raw_reaction_remove event listeners."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage
from modules.reactionrole import ReactionRole
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    """Load locale YAML files before each test."""
    load_strings()


@pytest.fixture
def cog(mock_bot):
    """Create a ReactionRole cog using __new__ to skip discord.py Cog init machinery."""
    c = ReactionRole.__new__(ReactionRole)
    c.bot = mock_bot
    return c


@pytest.fixture
def guild_id():
    return 987654321


@pytest.fixture
def message_id():
    return 112233445566


@pytest.fixture
def role_id():
    return 111


@pytest.fixture
def mock_role(role_id):
    role = MagicMock()
    role.id = role_id
    role.name = "TestRole"
    return role


@pytest.fixture
def db_with_reaction_role(db_session, guild_id, message_id, role_id):
    """Insert a ReactionRoleMessage + ReactionRoleEntry for 👍 -> role_id."""
    rr_msg = ReactionRoleMessage(GuildId=guild_id, ChannelId=555, MessageId=message_id)
    db_session.add(rr_msg)
    db_session.flush()
    db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=role_id))
    db_session.commit()
    return rr_msg


def _make_payload(message_id, guild_id, emoji_name, member=None, user_id=999):
    """Build a minimal RawReactionActionEvent-like mock."""
    payload = MagicMock()
    payload.message_id = message_id
    payload.guild_id = guild_id
    payload.user_id = user_id
    payload.member = member

    emoji = MagicMock()
    emoji.name = emoji_name
    emoji.__str__ = lambda _: emoji_name
    payload.emoji = emoji

    return payload


class TestOnRawReactionAdd:
    """Tests for the on_raw_reaction_add listener."""

    @pytest.mark.asyncio
    async def test_reaction_add_assigns_role(self, cog, db_with_reaction_role, guild_id, message_id, mock_role):
        """Adding a known reaction should assign the mapped role to the member."""
        member = MagicMock()
        member.bot = False
        member.add_roles = AsyncMock()

        payload = _make_payload(message_id, guild_id, "👍", member=member)

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_role = MagicMock(return_value=mock_role)
        cog.bot.get_guild = MagicMock(return_value=mock_guild)

        await cog.on_raw_reaction_add(payload)

        member.add_roles.assert_awaited_once_with(mock_role, reason="Reaction role")

    @pytest.mark.asyncio
    async def test_reaction_add_unknown_message_does_nothing(self, cog, guild_id):
        """A reaction on an unknown message_id should not assign any role."""
        member = MagicMock()
        member.bot = False
        member.add_roles = AsyncMock()

        payload = _make_payload(message_id=999999, guild_id=guild_id, emoji_name="👍", member=member)

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        cog.bot.get_guild = MagicMock(return_value=mock_guild)

        # Should not raise and should not add any roles
        await cog.on_raw_reaction_add(payload)

        member.add_roles.assert_not_called()


class TestOnRawReactionRemove:
    """Tests for the on_raw_reaction_remove listener."""

    @pytest.mark.asyncio
    async def test_reaction_remove_removes_role(self, cog, db_with_reaction_role, guild_id, message_id, mock_role):
        """Removing a known reaction should remove the mapped role from the member."""
        user_id = 777888999

        member = MagicMock()
        member.bot = False
        member.remove_roles = AsyncMock()

        payload = _make_payload(message_id, guild_id, "👍", member=None, user_id=user_id)

        mock_guild = MagicMock()
        mock_guild.id = guild_id
        mock_guild.name = "Test Guild"
        mock_guild.get_member = MagicMock(return_value=member)
        mock_guild.get_role = MagicMock(return_value=mock_role)
        cog.bot.get_guild = MagicMock(return_value=mock_guild)

        await cog.on_raw_reaction_remove(payload)

        member.remove_roles.assert_awaited_once_with(mock_role, reason="Reaction role")
