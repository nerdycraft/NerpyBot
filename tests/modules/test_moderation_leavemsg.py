# -*- coding: utf-8 -*-
"""Tests for modules.moderation — leavemsg sub-group commands."""

from unittest.mock import MagicMock

import pytest
from models.leavemsg import LeaveMessage
from modules.moderation import Moderation
from utils.errors import NerpyValidationError
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


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


# ---------------------------------------------------------------------------
# /moderation leavemsg enable
# ---------------------------------------------------------------------------


class TestLeavemsgEnable:
    async def test_enable_creates_config(self, cog, interaction, db_session):
        channel = MagicMock()
        channel.id = 111
        channel.mention = "<#111>"
        channel.permissions_for.return_value = MagicMock(view_channel=True, send_messages=True)

        await Moderation.leavemsg._children["enable"].callback(cog, interaction, channel)

        interaction.response.send_message.assert_awaited_once()
        msg = interaction.response.send_message.call_args[0][0]
        assert "<#111>" in msg
        assert "enabled" in msg.lower() or "aktiviert" in msg.lower()

        config = db_session.query(LeaveMessage).filter_by(GuildId=987654321).first()
        assert config is not None
        assert config.Enabled is True
        assert config.ChannelId == 111

    async def test_enable_updates_existing(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=222, Enabled=False))
        db_session.commit()

        channel = MagicMock()
        channel.id = 333
        channel.mention = "<#333>"
        channel.permissions_for.return_value = MagicMock(view_channel=True, send_messages=True)

        await Moderation.leavemsg._children["enable"].callback(cog, interaction, channel)

        config = db_session.query(LeaveMessage).filter_by(GuildId=987654321).first()
        assert config.ChannelId == 333
        assert config.Enabled is True


# ---------------------------------------------------------------------------
# /moderation leavemsg disable
# ---------------------------------------------------------------------------


class TestLeavemsgDisable:
    async def test_disable_success(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        await Moderation.leavemsg._children["disable"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "disabled" in msg.lower() or "deaktiviert" in msg.lower()

    async def test_disable_not_configured(self, cog, interaction):
        with pytest.raises(NerpyValidationError, match="not configured|nicht konfiguriert"):
            await Moderation.leavemsg._children["disable"].callback(cog, interaction)


# ---------------------------------------------------------------------------
# /moderation leavemsg message
# ---------------------------------------------------------------------------


class TestLeavemsgMessage:
    async def test_set_message_success(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        await Moderation.leavemsg._children["message"].callback(cog, interaction, "Goodbye {member}!")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Goodbye {member}!" in msg

        config = db_session.query(LeaveMessage).filter_by(GuildId=987654321).first()
        assert config.Message == "Goodbye {member}!"

    async def test_set_message_missing_placeholder(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        with pytest.raises(NerpyValidationError, match="\\{member\\}"):
            await Moderation.leavemsg._children["message"].callback(cog, interaction, "No placeholder here")

    async def test_set_message_not_enabled(self, cog, interaction):
        with pytest.raises(NerpyValidationError, match="enable|aktiviere"):
            await Moderation.leavemsg._children["message"].callback(cog, interaction, "Bye {member}")


# ---------------------------------------------------------------------------
# /moderation leavemsg status
# ---------------------------------------------------------------------------


class TestLeavemsgStatus:
    async def test_status_not_enabled(self, cog, interaction):
        await Moderation.leavemsg._children["status"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "not enabled" in msg.lower() or "nicht aktiviert" in msg.lower()

    async def test_status_enabled(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Message="Bye {member}", Enabled=True))
        db_session.commit()

        channel = MagicMock()
        channel.mention = "<#111>"
        interaction.guild.get_channel = MagicMock(return_value=channel)

        await Moderation.leavemsg._children["status"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "<#111>" in msg
        assert "Bye {member}" in msg
