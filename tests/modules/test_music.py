# -*- coding: utf-8 -*-
"""Tests for modules.music — localized music command responses."""

from unittest.mock import MagicMock

import pytest
from models.admin import GuildLanguageConfig
from modules.music import Music
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    mock_bot.config = {"music": {"ytkey": "fake-key"}}
    mock_bot.audio = MagicMock()
    mock_bot.audio.stop = MagicMock()
    cog = Music.__new__(Music)
    cog.bot = mock_bot
    cog.config = mock_bot.config["music"]
    cog.queue = {}
    cog.audio = mock_bot.audio
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


# ---------------------------------------------------------------------------
# /music skip
# ---------------------------------------------------------------------------


class TestSkip:
    async def test_skip_sends_confirmation(self, cog, interaction):
        await Music._skip_audio.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Skipped" in msg
        cog.audio.stop.assert_called_once_with(987654321)

    async def test_skip_german(self, cog, interaction, db_session):
        db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
        db_session.commit()

        await Music._skip_audio.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "übersprungen" in msg


# ---------------------------------------------------------------------------
# /music queue drop
# ---------------------------------------------------------------------------


class TestQueueDrop:
    async def test_drop_sends_confirmation(self, cog, interaction):
        await Music._drop_queue.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Cleared" in msg

    async def test_drop_german(self, cog, interaction, db_session):
        db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
        db_session.commit()

        await Music._drop_queue.callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Warteschlange" in msg


# ---------------------------------------------------------------------------
# /music play search (no results)
# ---------------------------------------------------------------------------


class TestSearchNoResults:
    async def test_no_results_english(self, cog, interaction, monkeypatch):
        monkeypatch.setattr("modules.music.youtube", lambda *a, **kw: None)

        await Music._search_music.callback(cog, interaction, "nonexistent song")

        msg = interaction.followup.send.call_args[1].get("content") or interaction.followup.send.call_args[0][0]
        assert "did not yield any results" in msg.lower()

    async def test_no_results_german(self, cog, interaction, db_session, monkeypatch):
        db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
        db_session.commit()

        monkeypatch.setattr("modules.music.youtube", lambda *a, **kw: None)

        await Music._search_music.callback(cog, interaction, "nonexistent song")

        msg = interaction.followup.send.call_args[1].get("content") or interaction.followup.send.call_args[0][0]
        assert "keine Ergebnisse" in msg


# ---------------------------------------------------------------------------
# playlist: not a playlist
# ---------------------------------------------------------------------------


class TestPlaylistNotAPlaylist:
    async def test_not_a_playlist_english(self, cog, interaction, monkeypatch):
        monkeypatch.setattr("modules.music.fetch_yt_infos", lambda url: {"title": "test", "id": "1"})

        await Music._add_playlist.callback(cog, interaction, "https://example.com/video")

        msg = interaction.followup.send.call_args[0][0]
        assert "not a playlist" in msg.lower()

    async def test_not_a_playlist_german(self, cog, interaction, db_session, monkeypatch):
        db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
        db_session.commit()

        monkeypatch.setattr("modules.music.fetch_yt_infos", lambda url: {"title": "test", "id": "1"})

        await Music._add_playlist.callback(cog, interaction, "https://example.com/video")

        msg = interaction.followup.send.call_args[0][0]
        assert "keine Playlist" in msg
