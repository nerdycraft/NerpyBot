# -*- coding: utf-8 -*-
"""Tests for modules.roles — reaction role commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage
from modules.roles import Roles
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture(autouse=True)
def _bypass_role_checks(monkeypatch):
    """Bypass is_role_below_bot — tested separately in test_checks.py."""

    async def _always_true(*_args, **_kwargs):
        return True

    monkeypatch.setattr("modules.roles.is_role_below_bot", _always_true)


@pytest.fixture
def cog(mock_bot):
    cog = Roles.__new__(Roles)
    cog.bot = mock_bot
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


@pytest.fixture
def channel():
    ch = MagicMock()
    ch.id = 111
    ch.name = "general"
    ch.mention = "#general"
    ch.permissions_for = MagicMock(
        return_value=MagicMock(view_channel=True, add_reactions=True, manage_messages=True, read_message_history=True)
    )
    ch.fetch_message = AsyncMock(return_value=MagicMock(add_reaction=AsyncMock()))
    return ch


@pytest.fixture
def role():
    r = MagicMock()
    r.id = 333
    r.name = "Member"
    return r


# ---------------------------------------------------------------------------
# /reactionrole add
# ---------------------------------------------------------------------------


class TestAdd:
    async def test_add_success(self, cog, interaction, channel, role):
        await Roles.reactionrole._children["add"].callback(cog, interaction, channel, "12345", "👍", role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Mapped" in msg
        assert "👍" in msg
        assert "Member" in msg

    async def test_add_updates_cache(self, cog, interaction, channel, role):
        cog.bot.guild_cache.warm_reaction_roles(cog.bot.SESSION)

        await Roles.reactionrole._children["add"].callback(cog, interaction, channel, "12345", "👍", role)

        assert cog.bot.guild_cache.get_reaction_role(12345, "👍") == role.id

    async def test_add_already_mapped(self, cog, interaction, channel, role, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        await Roles.reactionrole._children["add"].callback(cog, interaction, channel, "12345", "👍", role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "already mapped" in msg


# ---------------------------------------------------------------------------
# /reactionrole remove
# ---------------------------------------------------------------------------


class TestRemove:
    async def test_remove_no_config(self, cog, interaction):
        await Roles.reactionrole._children["remove"].callback(cog, interaction, "99999", "👍")

        msg = interaction.response.send_message.call_args[0][0]
        assert "No reaction role config" in msg

    async def test_remove_success(self, cog, interaction, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        cog._clear_reaction = AsyncMock()

        await Roles.reactionrole._children["remove"].callback(cog, interaction, "12345", "👍")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Removed mapping" in msg

    async def test_remove_last_entry_evicts_message_from_cache(self, cog, interaction, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        cog.bot.guild_cache.warm_reaction_roles(cog.bot.SESSION)
        cog._clear_reaction = AsyncMock()

        await Roles.reactionrole._children["remove"].callback(cog, interaction, "12345", "👍")

        assert cog.bot.guild_cache.is_reaction_role_message(12345) is False

    async def test_remove_non_last_entry_keeps_message_tracked(self, cog, interaction, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="❤️", RoleId=444))
        db_session.commit()

        cog.bot.guild_cache.warm_reaction_roles(cog.bot.SESSION)
        cog._clear_reaction = AsyncMock()

        await Roles.reactionrole._children["remove"].callback(cog, interaction, "12345", "👍")

        assert cog.bot.guild_cache.is_reaction_role_message(12345) is True
        assert cog.bot.guild_cache.get_reaction_role(12345, "👍") is None


# ---------------------------------------------------------------------------
# /reactionrole list
# ---------------------------------------------------------------------------


class TestList:
    async def test_list_empty(self, cog, interaction):
        await Roles.reactionrole._children["list"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No reaction roles configured" in msg


# ---------------------------------------------------------------------------
# /reactionrole clear
# ---------------------------------------------------------------------------


class TestClear:
    async def test_clear_no_config(self, cog, interaction):
        await Roles.reactionrole._children["clear"].callback(cog, interaction, "99999")

        msg = interaction.response.send_message.call_args[0][0]
        assert "No reaction role config" in msg

    async def test_clear_success(self, cog, interaction, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        cog._clear_reaction = AsyncMock()

        await Roles.reactionrole._children["clear"].callback(cog, interaction, "12345")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Cleared all" in msg
