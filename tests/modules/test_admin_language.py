# -*- coding: utf-8 -*-
"""Tests for /language set and /language get admin commands."""

import pytest
import yaml

from models.admin import GuildLanguageConfig
from utils import strings


@pytest.fixture(autouse=True)
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


@pytest.fixture
def admin_cog(mock_bot):
    """Create an Admin cog instance."""
    from modules.admin import Admin

    cog = Admin.__new__(Admin)
    cog.bot = mock_bot
    return cog


class TestLanguageSet:
    @pytest.mark.asyncio
    async def test_set_valid_language(self, admin_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        await admin_cog._language_set.callback(admin_cog, mock_interaction, language="de")

        config = GuildLanguageConfig.get(123, db_session)
        assert config is not None
        assert config.Language == "de"

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "de" in call_args

    @pytest.mark.asyncio
    async def test_set_overwrites_existing(self, admin_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        db_session.add(GuildLanguageConfig(GuildId=123, Language="en"))
        db_session.commit()

        await admin_cog._language_set.callback(admin_cog, mock_interaction, language="de")

        config = GuildLanguageConfig.get(123, db_session)
        assert config.Language == "de"

    @pytest.mark.asyncio
    async def test_set_invalid_language(self, admin_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        await admin_cog._language_set.callback(admin_cog, mock_interaction, language="xx")

        config = GuildLanguageConfig.get(123, db_session)
        assert config is None

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "xx" in call_args

    @pytest.mark.asyncio
    async def test_set_normalizes_case(self, admin_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        await admin_cog._language_set.callback(admin_cog, mock_interaction, language="DE")

        config = GuildLanguageConfig.get(123, db_session)
        assert config is not None
        assert config.Language == "de"


class TestLanguageGet:
    @pytest.mark.asyncio
    async def test_get_configured(self, admin_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        db_session.add(GuildLanguageConfig(GuildId=123, Language="de"))
        db_session.commit()

        await admin_cog._language_get.callback(admin_cog, mock_interaction)

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "de" in call_args

    @pytest.mark.asyncio
    async def test_get_default(self, admin_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123

        await admin_cog._language_get.callback(admin_cog, mock_interaction)

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "english" in call_args.lower() or "English" in call_args


class TestLanguageAutocomplete:
    @pytest.mark.asyncio
    async def test_autocomplete_filters_by_current(self, admin_cog, mock_interaction):
        choices = await admin_cog._language_autocomplete(mock_interaction, "d")
        names = [c.name for c in choices]
        assert "de" in names
        assert "en" not in names

    @pytest.mark.asyncio
    async def test_autocomplete_returns_all_on_empty(self, admin_cog, mock_interaction):
        choices = await admin_cog._language_autocomplete(mock_interaction, "")
        assert len(choices) == 2  # en and de from test locales
