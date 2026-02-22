# -*- coding: utf-8 -*-
"""Tests for modules.reactionrole — localized reaction role responses."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from models.admin import GuildLanguageConfig
from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage
from modules.reactionrole import ReactionRole
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture(autouse=True)
def _bypass_role_checks(monkeypatch):
    """Bypass is_role_below_bot — tested separately in test_checks.py."""

    async def _always_true(*_args, **_kwargs):
        return True

    monkeypatch.setattr("modules.reactionrole.is_role_below_bot", _always_true)


@pytest.fixture
def cog(mock_bot):
    cog = ReactionRole.__new__(ReactionRole)
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


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
    db_session.commit()


# ---------------------------------------------------------------------------
# /reactionrole add
# ---------------------------------------------------------------------------


class TestAdd:
    async def test_add_success(self, cog, interaction, channel, role):
        await ReactionRole._add.callback(cog, interaction, channel, "12345", "👍", role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Mapped" in msg
        assert "👍" in msg
        assert "Member" in msg

    async def test_add_already_mapped(self, cog, interaction, channel, role, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        await ReactionRole._add.callback(cog, interaction, channel, "12345", "👍", role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "already mapped" in msg

    async def test_add_german(self, cog, interaction, channel, role, db_session):
        _set_german(db_session)

        await ReactionRole._add.callback(cog, interaction, channel, "12345", "👍", role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "zugeordnet" in msg


# ---------------------------------------------------------------------------
# /reactionrole remove
# ---------------------------------------------------------------------------


class TestRemove:
    async def test_remove_no_config(self, cog, interaction):
        await ReactionRole._remove.callback(cog, interaction, "99999", "👍")

        msg = interaction.response.send_message.call_args[0][0]
        assert "No reaction role config" in msg

    async def test_remove_success(self, cog, interaction, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        # Mock _clear_reaction to avoid Discord API calls
        cog._clear_reaction = AsyncMock()

        await ReactionRole._remove.callback(cog, interaction, "12345", "👍")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Removed mapping" in msg

    async def test_remove_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await ReactionRole._remove.callback(cog, interaction, "99999", "👍")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Reaktionsrollen-Konfiguration" in msg


# ---------------------------------------------------------------------------
# /reactionrole list
# ---------------------------------------------------------------------------


class TestList:
    async def test_list_empty(self, cog, interaction):
        await ReactionRole._list.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No reaction roles configured" in msg

    async def test_list_empty_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await ReactionRole._list.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Reaktionsrollen konfiguriert" in msg


# ---------------------------------------------------------------------------
# /reactionrole clear
# ---------------------------------------------------------------------------


class TestClear:
    async def test_clear_no_config(self, cog, interaction):
        await ReactionRole._clear.callback(cog, interaction, "99999")

        msg = interaction.response.send_message.call_args[0][0]
        assert "No reaction role config" in msg

    async def test_clear_success(self, cog, interaction, db_session):
        rr_msg = ReactionRoleMessage(GuildId=987654321, ChannelId=111, MessageId=12345)
        db_session.add(rr_msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=rr_msg.Id, Emoji="👍", RoleId=333))
        db_session.commit()

        cog._clear_reaction = AsyncMock()

        await ReactionRole._clear.callback(cog, interaction, "12345")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Cleared all" in msg

    async def test_clear_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await ReactionRole._clear.callback(cog, interaction, "99999")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Reaktionsrollen-Konfiguration" in msg
