# -*- coding: utf-8 -*-
"""Tests for moderation module — localized responses."""

from unittest.mock import MagicMock

import pytest
from models.admin import GuildLanguageConfig
from models.moderation import AutoDelete
from modules.moderation import Moderation
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    cog = Moderation.__new__(Moderation)
    cog.bot = mock_bot
    cog._autokicker_loop = MagicMock()
    cog._autodeleter_loop = MagicMock()
    cog._autokicker_loop.start = MagicMock()
    cog._autodeleter_loop.start = MagicMock()
    cog._autokicker_loop.cancel = MagicMock()
    cog._autodeleter_loop.cancel = MagicMock()
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    mock_interaction.guild.get_channel = MagicMock(return_value=mock_interaction.channel)
    mock_interaction.channel.permissions_for = MagicMock(
        return_value=MagicMock(view_channel=True, send_messages=True, manage_messages=True, read_message_history=True)
    )
    return mock_interaction


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
    db_session.commit()


def _make_channel_mock(channel_id=555, name="test-channel"):
    ch = MagicMock()
    ch.id = channel_id
    ch.name = name
    ch.mention = f"<#{channel_id}>"
    ch.permissions_for = MagicMock(
        return_value=MagicMock(view_channel=True, send_messages=True, manage_messages=True, read_message_history=True)
    )
    return ch


# ---------------------------------------------------------------------------
# /moderation autokicker
# ---------------------------------------------------------------------------


class TestAutokicker:
    async def test_configured_english(self, cog, interaction, db_session):
        await Moderation.autokicker.callback(cog, interaction, enable=True, kick_after="1 day")
        msg = interaction.response.send_message.call_args[0][0]
        assert "AutoKicker configured" in msg

    async def test_configured_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Moderation.autokicker.callback(cog, interaction, enable=True, kick_after="1 day")
        msg = interaction.response.send_message.call_args[0][0]
        assert "AutoKicker für diesen Server konfiguriert" in msg

    async def test_invalid_timespan_english(self, cog, interaction, db_session):
        await Moderation.autokicker.callback(cog, interaction, enable=True, kick_after="invalid")
        msg = interaction.response.send_message.call_args[0][0]
        assert "Only timespans" in msg

    async def test_invalid_timespan_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Moderation.autokicker.callback(cog, interaction, enable=True, kick_after="invalid")
        msg = interaction.response.send_message.call_args[0][0]
        assert "nur Zeiträume" in msg


# ---------------------------------------------------------------------------
# /moderation autodeleter create
# ---------------------------------------------------------------------------


class TestAutodeleterCreate:
    async def test_create_english(self, cog, interaction, db_session):
        channel = _make_channel_mock()
        await Moderation._autodeleter_create.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "AutoDeleter configured" in msg
        assert "test-channel" in msg

    async def test_create_german(self, cog, interaction, db_session):
        _set_german(db_session)
        channel = _make_channel_mock()
        await Moderation._autodeleter_create.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "AutoDeleter für Kanal" in msg

    async def test_create_already_exists(self, cog, interaction, db_session):
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=True))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_create.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "already configured" in msg

    async def test_create_already_exists_german(self, cog, interaction, db_session):
        _set_german(db_session)
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=True))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_create.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "bereits für AutoDelete konfiguriert" in msg


# ---------------------------------------------------------------------------
# /moderation autodeleter delete
# ---------------------------------------------------------------------------


class TestAutodeleterDelete:
    async def test_delete_english(self, cog, interaction, db_session):
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=True))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_delete.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Deleted configuration" in msg

    async def test_delete_not_found_german(self, cog, interaction, db_session):
        _set_german(db_session)
        channel = _make_channel_mock()
        await Moderation._autodeleter_delete.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Konfiguration für Kanal" in msg


# ---------------------------------------------------------------------------
# /moderation autodeleter list
# ---------------------------------------------------------------------------


class TestAutodeleterList:
    async def test_list_empty_english(self, cog, interaction, db_session):
        await Moderation._autodeleter_list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No configuration found" in msg

    async def test_list_empty_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await Moderation._autodeleter_list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Konfiguration gefunden" in msg


# ---------------------------------------------------------------------------
# /moderation autodeleter pause
# ---------------------------------------------------------------------------


class TestAutodeleterPause:
    async def test_pause_no_config_english(self, cog, interaction, db_session):
        channel = _make_channel_mock()
        await Moderation._autodeleter_pause.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No auto-delete config" in msg

    async def test_pause_already_paused_german(self, cog, interaction, db_session):
        _set_german(db_session)
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=False))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_pause.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "bereits pausiert" in msg

    async def test_pause_success_english(self, cog, interaction, db_session):
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=True))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_pause.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Paused auto-deletion" in msg


# ---------------------------------------------------------------------------
# /moderation autodeleter resume
# ---------------------------------------------------------------------------


class TestAutodeleterResume:
    async def test_resume_already_active_german(self, cog, interaction, db_session):
        _set_german(db_session)
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=True))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_resume.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "bereits aktiv" in msg

    async def test_resume_success_english(self, cog, interaction, db_session):
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=False))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_resume.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Resumed auto-deletion" in msg


# ---------------------------------------------------------------------------
# /moderation autodeleter edit
# ---------------------------------------------------------------------------


class TestAutodeleterEdit:
    async def test_edit_not_found_german(self, cog, interaction, db_session):
        _set_german(db_session)
        channel = _make_channel_mock()
        await Moderation._autodeleter_modify.callback(cog, interaction, channel=channel)
        msg = interaction.response.send_message.call_args[0][0]
        assert "existiert nicht" in msg

    async def test_edit_success_english(self, cog, interaction, db_session):
        db_session.add(AutoDelete(GuildId=987654321, ChannelId=555, Enabled=True))
        db_session.commit()
        channel = _make_channel_mock()
        await Moderation._autodeleter_modify.callback(cog, interaction, channel=channel, keep_messages=10)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Updated configuration" in msg


# ---------------------------------------------------------------------------
# /moderation membercount
# ---------------------------------------------------------------------------


class TestMembercount:
    async def test_membercount_english(self, cog, interaction, db_session):
        interaction.guild.member_count = 42
        await Moderation.membercount.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "42" in emb.description
        assert "members" in emb.description

    async def test_membercount_german(self, cog, interaction, db_session):
        _set_german(db_session)
        interaction.guild.member_count = 42
        await Moderation.membercount.callback(cog, interaction)
        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "42" in emb.description
        assert "Mitglieder" in emb.description
