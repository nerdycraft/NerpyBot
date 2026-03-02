# -*- coding: utf-8 -*-
"""Tests for modules.music — localized music command responses."""

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture
def music_cog_new(mock_bot):
    """Create a Music cog (new design) with loops stopped."""
    mock_bot.config = {"music": {"ytkey": "fake-key"}}
    mock_bot.audio = MagicMock()
    mock_bot.audio.stop = MagicMock()
    mock_bot.audio.is_paused = MagicMock(return_value=False)
    mock_bot.audio.now_playing_message = {}
    mock_bot.audio.current_song = {}
    mock_bot.audio.play_start = {}
    mock_bot.audio.paused_at = {}
    mock_bot.audio.list_queue = MagicMock(return_value=[])
    mock_bot.audio.get_elapsed = MagicMock(return_value=30.0)
    mock_bot.audio._on_song_start_hook = None

    with patch.object(Music, "_progress_updater"):
        cog = Music.__new__(Music)
        cog.bot = mock_bot
        cog.config = mock_bot.config["music"]
        cog.audio = mock_bot.audio
        cog._progress_updater = MagicMock()
        cog._progress_updater.start = MagicMock()
        cog._progress_updater.cancel = MagicMock()
    return cog


class TestMusicHookAndProgressLoop:
    @pytest.mark.asyncio
    async def test_handle_song_start_new_session_sends_message(self, music_cog_new, db_session):
        """When now_playing_message is None/absent, a new message should be sent to the voice channel."""
        guild_id = 987654321
        music_cog_new.audio.now_playing_message = {}  # no existing message

        song = MagicMock()
        song.title = "Test Song"
        song.fetch_data = "https://youtube.com/watch?v=test"
        song.duration = 180
        song.requester = None
        song.thumbnail = None
        song.channel = MagicMock()
        song.channel.send = AsyncMock(return_value=MagicMock())

        await music_cog_new._handle_song_start(guild_id, song)

        song.channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_song_start_existing_session_edits_message(self, music_cog_new, db_session):
        """When now_playing_message exists, it should be edited rather than a new one sent."""
        guild_id = 987654321
        existing_msg = AsyncMock()
        existing_msg.edit = AsyncMock()
        music_cog_new.audio.now_playing_message = {guild_id: existing_msg}

        song = MagicMock()
        song.title = "Next Song"
        song.fetch_data = "https://youtube.com/watch?v=next"
        song.duration = 240
        song.requester = None
        song.thumbnail = None
        song.channel = MagicMock()
        song.channel.send = AsyncMock()

        await music_cog_new._handle_song_start(guild_id, song)

        existing_msg.edit.assert_called_once()
        song.channel.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_song_start_not_found_falls_back_to_send(self, music_cog_new, db_session):
        """When edit raises NotFound, a new message should be sent and stored."""
        import discord as _discord

        guild_id = 987654321
        existing_msg = AsyncMock()
        existing_msg.edit = AsyncMock(
            side_effect=_discord.NotFound(MagicMock(status=404, reason="Not Found"), "not found")
        )
        new_msg = MagicMock()
        music_cog_new.audio.now_playing_message = {guild_id: existing_msg}

        song = MagicMock()
        song.title = "New Song"
        song.fetch_data = "https://youtube.com/watch?v=new"
        song.duration = 120
        song.requester = None
        song.thumbnail = None
        song.channel = MagicMock()
        song.channel.send = AsyncMock(return_value=new_msg)

        await music_cog_new._handle_song_start(guild_id, song)

        song.channel.send.assert_called_once()
        assert music_cog_new.audio.now_playing_message[guild_id] is new_msg
