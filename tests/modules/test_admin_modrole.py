# -*- coding: utf-8 -*-
"""Tests for admin modrole and botpermissions — localized responses."""

from unittest.mock import MagicMock

import pytest
from models.admin import BotModeratorRole, GuildLanguageConfig, PermissionSubscriber
from modules.admin import Admin
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    cog = Admin.__new__(Admin)
    cog.bot = mock_bot
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    mock_interaction.user.id = 123456789
    return mock_interaction


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
    db_session.commit()


# ---------------------------------------------------------------------------
# /admin modrole get
# ---------------------------------------------------------------------------


class TestModroleGet:
    async def test_get_current(self, cog, interaction, db_session):
        db_session.add(BotModeratorRole(GuildId=987654321, RoleId=555))
        db_session.commit()
        role_mock = MagicMock()
        role_mock.name = "Mods"
        interaction.guild.get_role = MagicMock(return_value=role_mock)

        await Admin._modrole_get.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Bot-moderator role" in msg
        assert "Mods" in msg

    async def test_get_none(self, cog, interaction):
        await Admin._modrole_get.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No bot-moderator role" in msg

    async def test_get_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await Admin._modrole_get.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Bot-Moderator-Rolle" in msg


# ---------------------------------------------------------------------------
# /admin modrole set
# ---------------------------------------------------------------------------


class TestModroleSet:
    async def test_set_success(self, cog, interaction):
        role = MagicMock()
        role.id = 555
        role.name = "Mods"

        await Admin._modrole_set.callback(cog, interaction, role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "set to" in msg
        assert "Mods" in msg

    async def test_set_german(self, cog, interaction, db_session):
        _set_german(db_session)
        role = MagicMock()
        role.id = 555
        role.name = "Mods"

        await Admin._modrole_set.callback(cog, interaction, role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "gesetzt" in msg


# ---------------------------------------------------------------------------
# /admin modrole delete
# ---------------------------------------------------------------------------


class TestModroleDelete:
    async def test_delete_success(self, cog, interaction):
        await Admin._modrole_del.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "removed" in msg

    async def test_delete_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await Admin._modrole_del.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "entfernt" in msg


# ---------------------------------------------------------------------------
# /admin botpermissions subscribe
# ---------------------------------------------------------------------------


class TestBotpermissionsSubscribe:
    async def test_subscribe_success(self, cog, interaction):
        await Admin._botpermissions_subscribe.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Subscribed" in msg

    async def test_subscribe_already(self, cog, interaction, db_session):
        db_session.add(PermissionSubscriber(GuildId=987654321, UserId=123456789))
        db_session.commit()

        await Admin._botpermissions_subscribe.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "already subscribed" in msg

    async def test_subscribe_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await Admin._botpermissions_subscribe.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Abonniert" in msg


# ---------------------------------------------------------------------------
# /admin botpermissions unsubscribe
# ---------------------------------------------------------------------------


class TestBotpermissionsUnsubscribe:
    async def test_unsubscribe_not_subscribed(self, cog, interaction):
        await Admin._botpermissions_unsubscribe.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "not subscribed" in msg

    async def test_unsubscribe_success(self, cog, interaction, db_session):
        db_session.add(PermissionSubscriber(GuildId=987654321, UserId=123456789))
        db_session.commit()

        await Admin._botpermissions_unsubscribe.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Unsubscribed" in msg

    async def test_unsubscribe_german(self, cog, interaction, db_session):
        _set_german(db_session)

        await Admin._botpermissions_unsubscribe.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht abonniert" in msg
