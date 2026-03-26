# -*- coding: utf-8 -*-
"""Tests for ServerAdmin cog: /language and /modrole commands."""

from unittest.mock import MagicMock

import pytest
import yaml

from models.guild import GuildLanguageConfig
from models.permissions import BotModeratorRole
from modules.server_admin import ServerAdmin
from utils import strings
from utils.strings import load_strings


# ---------------------------------------------------------------------------
# Language fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _load_test_locales(tmp_path):
    """Load minimal locale files for testing."""
    en = {
        "admin": {
            "language": {
                "set_success": "Server language set to **{language}**.",
                "get_current": "Server language: **{language}**",
                "get_default": "No language configured. Defaulting to English.",
                "invalid": "Unsupported language: `{language}`. Available: {available}",
            }
        }
    }
    de = {
        "admin": {
            "language": {
                "set_success": "Serversprache auf **{language}** gesetzt.",
                "get_current": "Serversprache: **{language}**",
                "get_default": "Keine Sprache konfiguriert. Standard ist Englisch.",
                "invalid": "Nicht unterstützte Sprache: `{language}`. Verfügbar: {available}",
            }
        }
    }
    (tmp_path / "lang_en.yaml").write_text(yaml.dump(en))
    (tmp_path / "lang_de.yaml").write_text(yaml.dump(de))
    strings.load_strings(tmp_path)
    yield
    strings._strings.clear()
    strings._available_languages.clear()


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    cog = ServerAdmin.__new__(ServerAdmin)
    cog.bot = mock_bot
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    mock_interaction.user.id = 123456789
    return mock_interaction


# ---------------------------------------------------------------------------
# /modrole get
# ---------------------------------------------------------------------------


class TestModroleGet:
    async def test_get_current(self, cog, interaction, db_session):
        db_session.add(BotModeratorRole(GuildId=987654321, RoleId=555))
        db_session.commit()
        role_mock = MagicMock()
        role_mock.name = "Mods"
        interaction.guild.get_role = MagicMock(return_value=role_mock)

        await ServerAdmin.modrole._children["get"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Bot-moderator role" in msg
        assert "Mods" in msg

    async def test_get_none(self, cog, interaction):
        await ServerAdmin.modrole._children["get"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "No bot-moderator role" in msg


# ---------------------------------------------------------------------------
# /modrole set
# ---------------------------------------------------------------------------


class TestModroleSet:
    async def test_set_success(self, cog, interaction):
        role = MagicMock()
        role.id = 555
        role.name = "Mods"

        await ServerAdmin.modrole._children["set"].callback(cog, interaction, role)

        msg = interaction.response.send_message.call_args[0][0]
        assert "set to" in msg
        assert "Mods" in msg


# ---------------------------------------------------------------------------
# /modrole delete
# ---------------------------------------------------------------------------


class TestModroleDelete:
    async def test_delete_success(self, cog, interaction):
        await ServerAdmin.modrole._children["delete"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "removed" in msg


# ---------------------------------------------------------------------------
# /language set
# ---------------------------------------------------------------------------


class TestLanguageSet:
    @pytest.mark.asyncio
    async def test_set_valid_language(self, cog, mock_interaction, db_session, _load_test_locales):
        mock_interaction.guild.id = 123
        await ServerAdmin.language._children["set"].callback(cog, mock_interaction, language="de")

        config = GuildLanguageConfig.get(123, db_session)
        assert config is not None
        assert config.Language == "de"

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "de" in call_args

    @pytest.mark.asyncio
    async def test_set_overwrites_existing(self, cog, mock_interaction, db_session, _load_test_locales):
        mock_interaction.guild.id = 123
        db_session.add(GuildLanguageConfig(GuildId=123, Language="en"))
        db_session.commit()

        await ServerAdmin.language._children["set"].callback(cog, mock_interaction, language="de")

        config = GuildLanguageConfig.get(123, db_session)
        assert config.Language == "de"

    @pytest.mark.asyncio
    async def test_set_invalid_language(self, cog, mock_interaction, db_session, _load_test_locales):
        mock_interaction.guild.id = 123
        await ServerAdmin.language._children["set"].callback(cog, mock_interaction, language="xx")

        config = GuildLanguageConfig.get(123, db_session)
        assert config is None

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "xx" in call_args

    @pytest.mark.asyncio
    async def test_set_normalizes_case(self, cog, mock_interaction, db_session, _load_test_locales):
        mock_interaction.guild.id = 123
        await ServerAdmin.language._children["set"].callback(cog, mock_interaction, language="DE")

        config = GuildLanguageConfig.get(123, db_session)
        assert config is not None
        assert config.Language == "de"


# ---------------------------------------------------------------------------
# /language get
# ---------------------------------------------------------------------------


class TestLanguageGet:
    @pytest.mark.asyncio
    async def test_get_configured(self, cog, mock_interaction, db_session, _load_test_locales):
        mock_interaction.guild.id = 123
        db_session.add(GuildLanguageConfig(GuildId=123, Language="de"))
        db_session.commit()

        await ServerAdmin.language._children["get"].callback(cog, mock_interaction)

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "de" in call_args

    @pytest.mark.asyncio
    async def test_get_default(self, cog, mock_interaction, db_session, _load_test_locales):
        mock_interaction.guild.id = 123

        await ServerAdmin.language._children["get"].callback(cog, mock_interaction)

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "english" in call_args.lower() or "English" in call_args


# ---------------------------------------------------------------------------
# /language autocomplete
# ---------------------------------------------------------------------------


class TestLanguageAutocomplete:
    @pytest.mark.asyncio
    async def test_autocomplete_filters_by_current(self, cog, mock_interaction, _load_test_locales):
        choices = await cog._language_autocomplete(mock_interaction, "d")
        names = [c.name for c in choices]
        assert "de" in names
        assert "en" not in names

    @pytest.mark.asyncio
    async def test_autocomplete_returns_all_on_empty(self, cog, mock_interaction, _load_test_locales):
        choices = await cog._language_autocomplete(mock_interaction, "")
        assert len(choices) == 2  # en and de from test locales
