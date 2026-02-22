# -*- coding: utf-8 -*-
"""Tests for wow module — localized responses."""

from unittest.mock import MagicMock

import pytest
from models.admin import GuildLanguageConfig
from models.wow import WowGuildNewsConfig
from modules.wow import WorldofWarcraft
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    cog = WorldofWarcraft.__new__(WorldofWarcraft)
    cog.bot = mock_bot
    cog.config = {"wow": {"wow_id": "test", "wow_secret": "test", "guild_news": {}}}
    cog.client_id = "test"
    cog.client_secret = "test"
    cog.regions = ["eu", "us"]
    cog._realm_cache = {}
    cog._realm_cache_lock = MagicMock()
    cog._guild_news_loop = MagicMock()
    cog._guild_news_loop.start = MagicMock()
    cog._guild_news_loop.cancel = MagicMock()
    cog._guild_news_loop.change_interval = MagicMock()
    cog._poll_interval = 15
    cog._mount_batch_size = 20
    cog._track_mounts = True
    cog._default_active_days = 7
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    mock_interaction.guild.get_channel = MagicMock(return_value=None)
    return mock_interaction


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
    db_session.commit()


def _add_config(db_session, config_id=1, enabled=True):
    cfg = WowGuildNewsConfig(
        GuildId=987654321,
        ChannelId=555,
        WowGuildName="test-guild",
        WowRealmSlug="blackrock",
        Region="eu",
        Language="en",
        Enabled=enabled,
    )
    db_session.add(cfg)
    db_session.commit()
    # SQLite auto-increments; return the actual ID
    return cfg.Id


# ---------------------------------------------------------------------------
# /wow guildnews remove
# ---------------------------------------------------------------------------


class TestGuildnewsRemove:
    async def test_not_found_english(self, cog, interaction, db_session):
        await WorldofWarcraft._guildnews_remove.callback(cog, interaction, config=999)
        msg = interaction.response.send_message.call_args[0][0]
        assert "not found" in msg
        assert "999" in msg

    async def test_not_found_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await WorldofWarcraft._guildnews_remove.callback(cog, interaction, config=999)
        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht gefunden" in msg

    async def test_success_english(self, cog, interaction, db_session):
        cfg_id = _add_config(db_session)
        await WorldofWarcraft._guildnews_remove.callback(cog, interaction, config=cfg_id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Removed tracking config" in msg

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        cfg_id = _add_config(db_session)
        await WorldofWarcraft._guildnews_remove.callback(cog, interaction, config=cfg_id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Tracking-Konfiguration" in msg
        assert "entfernt" in msg


# ---------------------------------------------------------------------------
# /wow guildnews list
# ---------------------------------------------------------------------------


class TestGuildnewsList:
    async def test_empty_english(self, cog, interaction, db_session):
        await WorldofWarcraft._guildnews_list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No guild news configs" in msg

    async def test_empty_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await WorldofWarcraft._guildnews_list.callback(cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Gilden-News-Konfigurationen" in msg


# ---------------------------------------------------------------------------
# /wow guildnews pause
# ---------------------------------------------------------------------------


class TestGuildnewsPause:
    async def test_not_found_english(self, cog, interaction, db_session):
        await WorldofWarcraft._guildnews_pause.callback(cog, interaction, config=999)
        msg = interaction.response.send_message.call_args[0][0]
        assert "not found" in msg

    async def test_success_english(self, cog, interaction, db_session):
        cfg_id = _add_config(db_session)
        await WorldofWarcraft._guildnews_pause.callback(cog, interaction, config=cfg_id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Paused tracking" in msg

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        cfg_id = _add_config(db_session)
        await WorldofWarcraft._guildnews_pause.callback(cog, interaction, config=cfg_id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "pausiert" in msg


# ---------------------------------------------------------------------------
# /wow guildnews resume
# ---------------------------------------------------------------------------


class TestGuildnewsResume:
    async def test_not_found_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await WorldofWarcraft._guildnews_resume.callback(cog, interaction, config=999)
        msg = interaction.response.send_message.call_args[0][0]
        assert "nicht gefunden" in msg

    async def test_success_english(self, cog, interaction, db_session):
        cfg_id = _add_config(db_session, enabled=False)
        await WorldofWarcraft._guildnews_resume.callback(cog, interaction, config=cfg_id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Resumed tracking" in msg

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        cfg_id = _add_config(db_session, enabled=False)
        await WorldofWarcraft._guildnews_resume.callback(cog, interaction, config=cfg_id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "fortgesetzt" in msg


# ---------------------------------------------------------------------------
# /wow guildnews edit
# ---------------------------------------------------------------------------


class TestGuildnewsEdit:
    async def test_nothing_to_change_english(self, cog, interaction, db_session):
        await WorldofWarcraft._guildnews_edit.callback(cog, interaction, config=1)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nothing to change" in msg

    async def test_nothing_to_change_german(self, cog, interaction, db_session):
        _set_german(db_session)
        await WorldofWarcraft._guildnews_edit.callback(cog, interaction, config=1)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nichts zu ändern" in msg

    async def test_not_found_english(self, cog, interaction, db_session):
        await WorldofWarcraft._guildnews_edit.callback(cog, interaction, config=999, active_days=14)
        msg = interaction.response.send_message.call_args[0][0]
        assert "not found" in msg

    async def test_success_english(self, cog, interaction, db_session):
        cfg_id = _add_config(db_session)
        await WorldofWarcraft._guildnews_edit.callback(cog, interaction, config=cfg_id, active_days=14)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Updated config" in msg
        assert "active_days" in msg

    async def test_success_german(self, cog, interaction, db_session):
        _set_german(db_session)
        cfg_id = _add_config(db_session)
        await WorldofWarcraft._guildnews_edit.callback(cog, interaction, config=cfg_id, active_days=14)
        msg = interaction.response.send_message.call_args[0][0]
        assert "aktualisiert" in msg
        assert "Aktive Tage" in msg
