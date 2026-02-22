# -*- coding: utf-8 -*-
"""Tests for modules.leavemsg — leave message commands."""

from unittest.mock import MagicMock

import pytest
from models.admin import GuildLanguageConfig
from models.leavemsg import LeaveMessage
from modules.leavemsg import LeaveMsg
from utils.errors import NerpyValidationError
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    """Load locale YAML files before each test."""
    load_strings()


@pytest.fixture
def cog(mock_bot):
    return LeaveMsg(mock_bot)


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


# ---------------------------------------------------------------------------
# /leavemsg enable
# ---------------------------------------------------------------------------


class TestLeavemsgEnable:
    async def test_enable_creates_config(self, cog, interaction, db_session):
        channel = MagicMock()
        channel.id = 111
        channel.mention = "<#111>"
        channel.permissions_for.return_value = MagicMock(view_channel=True, send_messages=True)

        await LeaveMsg._leavemsg_enable.callback(cog, interaction, channel)

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

        await LeaveMsg._leavemsg_enable.callback(cog, interaction, channel)

        config = db_session.query(LeaveMessage).filter_by(GuildId=987654321).first()
        assert config.ChannelId == 333
        assert config.Enabled is True


# ---------------------------------------------------------------------------
# /leavemsg disable
# ---------------------------------------------------------------------------


class TestLeavemsgDisable:
    async def test_disable_success(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        await LeaveMsg._leavemsg_disable.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "disabled" in msg.lower() or "deaktiviert" in msg.lower()

    async def test_disable_not_configured(self, cog, interaction):
        with pytest.raises(NerpyValidationError, match="not configured|nicht konfiguriert"):
            await LeaveMsg._leavemsg_disable.callback(cog, interaction)


# ---------------------------------------------------------------------------
# /leavemsg message
# ---------------------------------------------------------------------------


class TestLeavemsgMessage:
    async def test_set_message_success(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        await LeaveMsg._leavemsg_message.callback(cog, interaction, "Goodbye {member}!")

        msg = interaction.response.send_message.call_args[0][0]
        assert "Goodbye {member}!" in msg

        config = db_session.query(LeaveMessage).filter_by(GuildId=987654321).first()
        assert config.Message == "Goodbye {member}!"

    async def test_set_message_missing_placeholder(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        with pytest.raises(NerpyValidationError, match="\\{member\\}"):
            await LeaveMsg._leavemsg_message.callback(cog, interaction, "No placeholder here")

    async def test_set_message_not_enabled(self, cog, interaction):
        with pytest.raises(NerpyValidationError, match="enable|aktiviere"):
            await LeaveMsg._leavemsg_message.callback(cog, interaction, "Bye {member}")


# ---------------------------------------------------------------------------
# /leavemsg status
# ---------------------------------------------------------------------------


class TestLeavemsgStatus:
    async def test_status_not_enabled(self, cog, interaction):
        await LeaveMsg._leavemsg_status.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "not enabled" in msg.lower() or "nicht aktiviert" in msg.lower()

    async def test_status_enabled(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Message="Bye {member}", Enabled=True))
        db_session.commit()

        channel = MagicMock()
        channel.mention = "<#111>"
        interaction.guild.get_channel = MagicMock(return_value=channel)

        await LeaveMsg._leavemsg_status.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "<#111>" in msg
        assert "Bye {member}" in msg


# ---------------------------------------------------------------------------
# Localization: German guild language
# ---------------------------------------------------------------------------


class TestLeavemsgLocalization:
    @pytest.fixture(autouse=True)
    def _set_german(self, db_session):
        db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
        db_session.commit()

    async def test_enable_returns_german(self, cog, interaction, db_session):
        channel = MagicMock()
        channel.id = 111
        channel.mention = "<#111>"
        channel.permissions_for.return_value = MagicMock(view_channel=True, send_messages=True)

        await LeaveMsg._leavemsg_enable.callback(cog, interaction, channel)

        msg = interaction.response.send_message.call_args[0][0]
        assert "aktiviert" in msg

    async def test_disable_not_configured_returns_german(self, cog, interaction):
        with pytest.raises(NerpyValidationError, match="nicht konfiguriert"):
            await LeaveMsg._leavemsg_disable.callback(cog, interaction)

    async def test_status_not_enabled_returns_german(self, cog, interaction):
        await LeaveMsg._leavemsg_status.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht aktiviert" in msg

    async def test_message_missing_placeholder_returns_german(self, cog, interaction, db_session):
        db_session.add(LeaveMessage(GuildId=987654321, ChannelId=111, Enabled=True))
        db_session.commit()

        with pytest.raises(NerpyValidationError, match="Platzhalter"):
            await LeaveMsg._leavemsg_message.callback(cog, interaction, "No placeholder")
