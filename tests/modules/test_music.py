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


class TestPlayCommand:
    @pytest.mark.asyncio
    async def test_play_single_song_queues_and_responds_ephemeral(self, music_cog_new, mock_interaction, monkeypatch):
        monkeypatch.setattr(
            "modules.music.fetch_yt_infos",
            lambda url: {
                "title": "Test Song",
                "id": "abc123",
                "duration": 210,
                "thumbnails": [{"url": "https://img.yt/thumb.jpg"}],
            },
        )
        music_cog_new.audio.play = AsyncMock()

        await Music._play.callback(music_cog_new, mock_interaction, "https://youtube.com/watch?v=abc123")

        music_cog_new.audio.play.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        assert mock_interaction.followup.send.call_args[1].get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_play_playlist_url_queues_all_entries(self, music_cog_new, mock_interaction, monkeypatch):
        entries = [
            {"webpage_url": "https://yt/1", "title": "A", "id": "1", "duration": 100, "thumbnails": []},
            {"webpage_url": "https://yt/2", "title": "B", "id": "2", "duration": 200, "thumbnails": []},
        ]

        def fake_fetch(url):
            if "playlist" in url:
                return {"_type": "playlist", "title": "My PL", "entries": entries}
            return {"title": url, "id": url[-1], "duration": 100, "thumbnails": []}

        monkeypatch.setattr("modules.music.fetch_yt_infos", fake_fetch)
        music_cog_new.audio.play = AsyncMock()

        await Music._play.callback(music_cog_new, mock_interaction, "https://youtube.com/playlist?list=PL")

        assert music_cog_new.audio.play.call_count == 2

    @pytest.mark.asyncio
    async def test_play_search_query_uses_youtube_helper(self, music_cog_new, mock_interaction, monkeypatch):
        monkeypatch.setattr("modules.music.youtube", lambda *a, **kw: "https://yt/found")
        monkeypatch.setattr(
            "modules.music.fetch_yt_infos",
            lambda url: {"title": "Found Song", "id": "xyz", "duration": 180, "thumbnails": []},
        )
        music_cog_new.audio.play = AsyncMock()

        await Music._play.callback(music_cog_new, mock_interaction, "some search query")

        music_cog_new.audio.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_play_search_no_results_sends_ephemeral_error(self, music_cog_new, mock_interaction, monkeypatch):
        monkeypatch.setattr("modules.music.youtube", lambda *a, **kw: None)

        await Music._play.callback(music_cog_new, mock_interaction, "unfindable query")

        mock_interaction.followup.send.assert_called_once()
        assert mock_interaction.followup.send.call_args[1].get("ephemeral") is True


from models.music import Playlist  # noqa: E402


class TestPlaylistCreate:
    @pytest.mark.asyncio
    async def test_create_stores_playlist(self, music_cog_new, mock_interaction, db_session):
        await Music.playlist._children["create"].callback(music_cog_new, mock_interaction, name="bops")
        p = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "bops", db_session)
        assert p is not None

    @pytest.mark.asyncio
    async def test_create_duplicate_sends_error(self, music_cog_new, mock_interaction, db_session):
        db_session.add(Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="dup"))
        db_session.commit()
        await Music.playlist._children["create"].callback(music_cog_new, mock_interaction, name="dup")
        if mock_interaction.followup.send.called:
            msg = mock_interaction.followup.send.call_args[0][0]
        else:
            msg = mock_interaction.response.send_message.call_args[0][0]
        assert "already" in msg.lower()

    @pytest.mark.asyncio
    async def test_create_responds_ephemeral(self, music_cog_new, mock_interaction, db_session):
        await Music.playlist._children["create"].callback(music_cog_new, mock_interaction, name="new")
        if mock_interaction.followup.send.called:
            assert mock_interaction.followup.send.call_args[1].get("ephemeral") is True


class TestPlaylistList:
    @pytest.mark.asyncio
    async def test_list_empty(self, music_cog_new, mock_interaction, db_session):
        await Music.playlist._children["list"].callback(music_cog_new, mock_interaction)
        if mock_interaction.followup.send.called:
            msg = mock_interaction.followup.send.call_args[0][0]
        else:
            msg = mock_interaction.response.send_message.call_args[0][0]
        assert "playlist" in msg.lower() or "no" in msg.lower()

    @pytest.mark.asyncio
    async def test_list_shows_names(self, music_cog_new, mock_interaction, db_session):
        db_session.add(Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="jazz"))
        db_session.commit()
        await Music.playlist._children["list"].callback(music_cog_new, mock_interaction)
        if mock_interaction.followup.send.called:
            content = str(mock_interaction.followup.send.call_args)
        else:
            content = str(mock_interaction.response.send_message.call_args)
        assert "jazz" in content


class TestPlaylistShow:
    @pytest.mark.asyncio
    async def test_show_not_found(self, music_cog_new, mock_interaction, db_session):
        await Music.playlist._children["show"].callback(music_cog_new, mock_interaction, name="missing")
        called = mock_interaction.followup.send.called or mock_interaction.response.send_message.called
        assert called
        if mock_interaction.followup.send.called:
            msg = mock_interaction.followup.send.call_args[0][0]
            assert "missing" in msg.lower() or "not found" in msg.lower()


from models.music import PlaylistEntry  # noqa: E402


class TestPlaylistAdd:
    @pytest.mark.asyncio
    async def test_add_creates_entry(self, music_cog_new, mock_interaction, db_session, monkeypatch):
        db_session.add(Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="favs"))
        db_session.commit()
        monkeypatch.setattr(
            "modules.music.fetch_yt_infos", lambda url: {"title": "My Song", "id": "1", "duration": 180}
        )

        await Music.playlist._children["add"].callback(music_cog_new, mock_interaction, name="favs", url="https://yt/1")

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "favs", db_session)
        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 1
        assert entries[0].Title == "My Song"

    @pytest.mark.asyncio
    async def test_add_playlist_not_found(self, music_cog_new, mock_interaction, db_session, monkeypatch):
        monkeypatch.setattr("modules.music.fetch_yt_infos", lambda url: {"title": "x", "id": "1"})
        await Music.playlist._children["add"].callback(
            music_cog_new, mock_interaction, name="missing", url="https://yt/1"
        )
        called = mock_interaction.followup.send.called or mock_interaction.response.send_message.called
        assert called


class TestPlaylistRemove:
    @pytest.mark.asyncio
    async def test_remove_deletes_entry(self, music_cog_new, mock_interaction, db_session):
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="del")
        db_session.add(pl)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://yt/1", Title="Gone", Position=0))
        db_session.commit()

        await Music.playlist._children["remove"].callback(
            music_cog_new, mock_interaction, name="del", url="https://yt/1"
        )

        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert entries == []

    @pytest.mark.asyncio
    async def test_remove_url_not_found_sends_error(self, music_cog_new, mock_interaction, db_session):
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="nodelmatch")
        db_session.add(pl)
        db_session.flush()
        db_session.commit()

        await Music.playlist._children["remove"].callback(
            music_cog_new, mock_interaction, name="nodelmatch", url="https://yt/nonexistent"
        )

        call_args = mock_interaction.followup.send.call_args
        assert "not found in the playlist" in call_args.args[0]


from collections import deque  # noqa: E402


def _make_song(title, url):
    s = MagicMock()
    s.title = title
    s.fetch_data = url
    return s


class TestPlaylistSave:
    @pytest.mark.asyncio
    async def test_save_current_queue(self, music_cog_new, mock_interaction, db_session):
        """No count -> saves current queue."""
        songs = [_make_song("A", "https://yt/a"), _make_song("B", "https://yt/b")]
        music_cog_new.audio.list_queue = MagicMock(return_value=songs)

        await Music.playlist._children["save"].callback(music_cog_new, mock_interaction, name="queue-snap")

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "queue-snap", db_session)
        assert pl is not None
        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 2
        assert entries[0].Title == "A"

    @pytest.mark.asyncio
    async def test_save_history_n_songs(self, music_cog_new, mock_interaction, db_session):
        """count=2 -> saves last 2 songs from history."""
        history = deque([_make_song("Old", "https://yt/old"), _make_song("New", "https://yt/new")], maxlen=50)
        music_cog_new.audio.history = {mock_interaction.guild_id: history}
        music_cog_new.audio.list_queue = MagicMock(return_value=[])

        await Music.playlist._children["save"].callback(music_cog_new, mock_interaction, name="history-snap", count=2)

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "history-snap", db_session)
        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_save_history_too_few_sends_error(self, music_cog_new, mock_interaction, db_session):
        music_cog_new.audio.history = {mock_interaction.guild_id: deque([_make_song("X", "u")], maxlen=50)}
        music_cog_new.audio.list_queue = MagicMock(return_value=[])

        await Music.playlist._children["save"].callback(music_cog_new, mock_interaction, name="oops", count=5)

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "oops", db_session)
        assert pl is None

    @pytest.mark.asyncio
    async def test_save_overwrites_existing_playlist(self, music_cog_new, mock_interaction, db_session):
        """Saving to an existing playlist name should replace its entries."""
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="replace-me")
        db_session.add(pl)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://old", Title="Old", Position=0))
        db_session.commit()

        songs = [_make_song("New", "https://new")]
        music_cog_new.audio.list_queue = MagicMock(return_value=songs)

        await Music.playlist._children["save"].callback(music_cog_new, mock_interaction, name="replace-me")

        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 1
        assert entries[0].Title == "New"
