# -*- coding: utf-8 -*-
"""Tests for modules.music — localized music command responses."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.music import Playlist, PlaylistEntry
from modules.music.playback import MusicPlayback
from modules.music.playlist import MusicPlaylist
from utils.cache import _autocomplete_cache
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def music_cog_new(mock_bot):
    """Create a MusicPlayback cog with loops stopped."""
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

    with patch.object(MusicPlayback, "_progress_updater"):
        cog = MusicPlayback.__new__(MusicPlayback)
        cog.bot = mock_bot
        cog.config = mock_bot.config["music"]
        cog.audio = mock_bot.audio
        cog._background_tasks = set()
        cog._progress_updater = MagicMock()
        cog._progress_updater.start = MagicMock()
        cog._progress_updater.cancel = MagicMock()
    return cog


@pytest.fixture
def playlist_cog(mock_bot):
    """Create a MusicPlaylist cog."""
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

    cog = MusicPlaylist.__new__(MusicPlaylist)
    cog.bot = mock_bot
    cog.audio = mock_bot.audio
    cog._background_tasks = set()
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
            "modules.music.playback.fetch_yt_infos",
            lambda url: {
                "title": "Test Song",
                "id": "abc123",
                "duration": 210,
                "thumbnails": [{"url": "https://img.yt/thumb.jpg"}],
            },
        )
        music_cog_new.audio.play = AsyncMock()

        await MusicPlayback._play.callback(music_cog_new, mock_interaction, "https://youtube.com/watch?v=abc123")

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

        monkeypatch.setattr("modules.music.playback.fetch_yt_infos", fake_fetch)
        mock_interaction.user.voice = MagicMock()
        mock_interaction.user.voice.channel = MagicMock()
        music_cog_new.audio.play = AsyncMock()

        await MusicPlayback._play.callback(music_cog_new, mock_interaction, "https://youtube.com/playlist?list=PL")
        # Drain background tasks spawned by create_task
        pending = music_cog_new._background_tasks
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        assert music_cog_new.audio.play.call_count == 2

    @pytest.mark.asyncio
    async def test_play_search_query_uses_youtube_helper(self, music_cog_new, mock_interaction, monkeypatch):
        monkeypatch.setattr("modules.music.playback.youtube", lambda *a, **kw: "https://yt/found")
        monkeypatch.setattr(
            "modules.music.playback.fetch_yt_infos",
            lambda url: {"title": "Found Song", "id": "xyz", "duration": 180, "thumbnails": []},
        )
        music_cog_new.audio.play = AsyncMock()

        await MusicPlayback._play.callback(music_cog_new, mock_interaction, "some search query")

        music_cog_new.audio.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_play_search_no_results_sends_ephemeral_error(self, music_cog_new, mock_interaction, monkeypatch):
        monkeypatch.setattr("modules.music.playback.youtube", lambda *a, **kw: None)

        await MusicPlayback._play.callback(music_cog_new, mock_interaction, "unfindable query")

        mock_interaction.followup.send.assert_called_once()
        assert mock_interaction.followup.send.call_args[1].get("ephemeral") is True


class TestPlaylistCreate:
    @pytest.mark.asyncio
    async def test_create_stores_playlist(self, playlist_cog, mock_interaction, db_session):
        guild_id = mock_interaction.guild_id
        user_id = mock_interaction.user.id
        _autocomplete_cache[("playlists", guild_id, user_id)] = ["stale"]

        await MusicPlaylist.playlist._children["create"].callback(playlist_cog, mock_interaction, name="bops")

        p = Playlist.get_by_name(guild_id, user_id, "bops", db_session)
        assert p is not None
        assert ("playlists", guild_id, user_id) not in _autocomplete_cache

    @pytest.mark.asyncio
    async def test_create_duplicate_sends_error(self, playlist_cog, mock_interaction, db_session):
        db_session.add(Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="dup"))
        db_session.commit()
        await MusicPlaylist.playlist._children["create"].callback(playlist_cog, mock_interaction, name="dup")
        if mock_interaction.followup.send.called:
            msg = mock_interaction.followup.send.call_args[0][0]
        else:
            msg = mock_interaction.response.send_message.call_args[0][0]
        assert "already" in msg.lower()

    @pytest.mark.asyncio
    async def test_create_responds_ephemeral(self, playlist_cog, mock_interaction, db_session):
        await MusicPlaylist.playlist._children["create"].callback(playlist_cog, mock_interaction, name="new")
        if mock_interaction.followup.send.called:
            assert mock_interaction.followup.send.call_args[1].get("ephemeral") is True


class TestPlaylistList:
    @pytest.mark.asyncio
    async def test_list_empty(self, playlist_cog, mock_interaction, db_session):
        await MusicPlaylist.playlist._children["list"].callback(playlist_cog, mock_interaction)
        if mock_interaction.followup.send.called:
            msg = mock_interaction.followup.send.call_args[0][0]
        else:
            msg = mock_interaction.response.send_message.call_args[0][0]
        assert "playlist" in msg.lower() or "no" in msg.lower()

    @pytest.mark.asyncio
    async def test_list_shows_names(self, playlist_cog, mock_interaction, db_session):
        db_session.add(Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="jazz"))
        db_session.commit()
        await MusicPlaylist.playlist._children["list"].callback(playlist_cog, mock_interaction)
        if mock_interaction.followup.send.called:
            content = str(mock_interaction.followup.send.call_args)
        else:
            content = str(mock_interaction.response.send_message.call_args)
        assert "jazz" in content


class TestPlaylistShow:
    @pytest.mark.asyncio
    async def test_show_not_found(self, playlist_cog, mock_interaction, db_session):
        await MusicPlaylist.playlist._children["show"].callback(playlist_cog, mock_interaction, name="missing")
        called = mock_interaction.followup.send.called or mock_interaction.response.send_message.called
        assert called
        if mock_interaction.followup.send.called:
            msg = mock_interaction.followup.send.call_args[0][0]
            assert "missing" in msg.lower() or "not found" in msg.lower()


class TestPlaylistAdd:
    @pytest.mark.asyncio
    async def test_add_creates_entry(self, playlist_cog, mock_interaction, db_session, monkeypatch):
        db_session.add(Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="favs"))
        db_session.commit()
        monkeypatch.setattr(
            "modules.music.playlist.fetch_yt_infos", lambda url: {"title": "My Song", "id": "1", "duration": 180}
        )

        await MusicPlaylist.playlist._children["add"].callback(
            playlist_cog, mock_interaction, name="favs", url="https://yt/1"
        )

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "favs", db_session)
        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 1
        assert entries[0].Title == "My Song"

    @pytest.mark.asyncio
    async def test_add_playlist_not_found(self, playlist_cog, mock_interaction, db_session, monkeypatch):
        monkeypatch.setattr("modules.music.playlist.fetch_yt_infos", lambda url: {"title": "x", "id": "1"})
        await MusicPlaylist.playlist._children["add"].callback(
            playlist_cog, mock_interaction, name="missing", url="https://yt/1"
        )
        called = mock_interaction.followup.send.called or mock_interaction.response.send_message.called
        assert called

    @pytest.mark.asyncio
    async def test_add_duplicate_url_sends_error(self, playlist_cog, mock_interaction, db_session, monkeypatch):
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="dupes")
        db_session.add(pl)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://yt/dup", Title="Dup", Position=0))
        db_session.commit()
        monkeypatch.setattr("modules.music.playlist.fetch_yt_infos", lambda url: {"title": "Dup", "id": "1"})

        await MusicPlaylist.playlist._children["add"].callback(
            playlist_cog, mock_interaction, name="dupes", url="https://yt/dup"
        )

        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 1  # not duplicated
        call_args = mock_interaction.followup.send.call_args
        assert "already" in call_args.args[0].lower()


class TestPlaylistDelete:
    @pytest.mark.asyncio
    async def test_delete_removes_playlist_and_entries(self, playlist_cog, mock_interaction, db_session):
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="gone")
        db_session.add(pl)
        db_session.flush()
        playlist_id = pl.Id
        db_session.add(PlaylistEntry(PlaylistId=playlist_id, Url="https://yt/1", Title="X", Position=0))
        db_session.commit()

        await MusicPlaylist.playlist._children["delete"].callback(playlist_cog, mock_interaction, name="gone")

        assert Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "gone", db_session) is None
        assert PlaylistEntry.get_by_playlist(playlist_id, db_session) == []

    @pytest.mark.asyncio
    async def test_delete_not_found_sends_error(self, playlist_cog, mock_interaction, db_session):
        await MusicPlaylist.playlist._children["delete"].callback(playlist_cog, mock_interaction, name="no-such-list")
        call_args = mock_interaction.followup.send.call_args
        assert "not found" in call_args.args[0].lower()


class TestPlaylistRemove:
    @pytest.mark.asyncio
    async def test_remove_deletes_entry(self, playlist_cog, mock_interaction, db_session):
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="del")
        db_session.add(pl)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://yt/1", Title="Gone", Position=0))
        db_session.commit()

        await MusicPlaylist.playlist._children["remove"].callback(
            playlist_cog, mock_interaction, name="del", url="https://yt/1"
        )

        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert entries == []

    @pytest.mark.asyncio
    async def test_remove_url_not_found_sends_error(self, playlist_cog, mock_interaction, db_session):
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="nodelmatch")
        db_session.add(pl)
        db_session.flush()
        db_session.commit()

        await MusicPlaylist.playlist._children["remove"].callback(
            playlist_cog, mock_interaction, name="nodelmatch", url="https://yt/nonexistent"
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
    async def test_save_current_queue(self, playlist_cog, mock_interaction, db_session):
        """No count -> saves current queue."""
        songs = [_make_song("A", "https://yt/a"), _make_song("B", "https://yt/b")]
        playlist_cog.audio.list_queue = MagicMock(return_value=songs)

        await MusicPlaylist.playlist._children["save"].callback(playlist_cog, mock_interaction, name="queue-snap")

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "queue-snap", db_session)
        assert pl is not None
        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 2
        assert entries[0].Title == "A"

    @pytest.mark.asyncio
    async def test_save_history_n_songs(self, playlist_cog, mock_interaction, db_session):
        """count=2 -> saves last 2 songs from history."""
        history = deque([_make_song("Old", "https://yt/old"), _make_song("New", "https://yt/new")], maxlen=50)
        playlist_cog.audio.history = {mock_interaction.guild_id: history}
        playlist_cog.audio.list_queue = MagicMock(return_value=[])

        await MusicPlaylist.playlist._children["save"].callback(
            playlist_cog, mock_interaction, name="history-snap", count=2
        )

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "history-snap", db_session)
        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 2

    @pytest.mark.asyncio
    async def test_save_history_too_few_sends_error(self, playlist_cog, mock_interaction, db_session):
        playlist_cog.audio.history = {mock_interaction.guild_id: deque([_make_song("X", "u")], maxlen=50)}
        playlist_cog.audio.list_queue = MagicMock(return_value=[])

        await MusicPlaylist.playlist._children["save"].callback(playlist_cog, mock_interaction, name="oops", count=5)

        pl = Playlist.get_by_name(mock_interaction.guild_id, mock_interaction.user.id, "oops", db_session)
        assert pl is None

    @pytest.mark.asyncio
    async def test_save_overwrites_existing_playlist(self, playlist_cog, mock_interaction, db_session):
        """Saving to an existing playlist name should replace its entries."""
        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="replace-me")
        db_session.add(pl)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://old", Title="Old", Position=0))
        db_session.commit()

        songs = [_make_song("New", "https://new")]
        playlist_cog.audio.list_queue = MagicMock(return_value=songs)

        await MusicPlaylist.playlist._children["save"].callback(playlist_cog, mock_interaction, name="replace-me")

        entries = PlaylistEntry.get_by_playlist(pl.Id, db_session)
        assert len(entries) == 1
        assert entries[0].Title == "New"


class TestPlaylistLoad:
    @pytest.mark.asyncio
    async def test_load_queues_all_entries(self, playlist_cog, mock_interaction, db_session, monkeypatch):
        from models.music import Playlist, PlaylistEntry  # noqa: E402

        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="mylist")
        db_session.add(pl)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://yt/1", Title="Song A", Position=0))
        db_session.add(PlaylistEntry(PlaylistId=pl.Id, Url="https://yt/2", Title="Song B", Position=1))
        db_session.commit()

        monkeypatch.setattr(
            "modules.music.playlist.fetch_yt_infos",
            lambda url: {"title": "Song", "id": url[-1], "duration": 120, "thumbnails": []},
        )
        playlist_cog.audio.play = AsyncMock()
        mock_interaction.user.voice = MagicMock()
        mock_interaction.user.voice.channel = MagicMock()

        await MusicPlaylist.playlist._children["load"].callback(playlist_cog, mock_interaction, name="mylist")
        # Drain background tasks spawned by create_task
        pending = playlist_cog._background_tasks
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        assert playlist_cog.audio.play.call_count == 2

    @pytest.mark.asyncio
    async def test_load_unknown_playlist_sends_error(self, playlist_cog, mock_interaction, db_session):
        mock_interaction.user.voice = MagicMock()

        await MusicPlaylist.playlist._children["load"].callback(playlist_cog, mock_interaction, name="no-such-list")

        call_args = mock_interaction.followup.send.call_args
        assert "not found" in call_args.args[0].lower()

    @pytest.mark.asyncio
    async def test_load_empty_playlist_sends_error(self, playlist_cog, mock_interaction, db_session):
        from models.music import Playlist  # noqa: E402

        pl = Playlist(GuildId=mock_interaction.guild_id, UserId=mock_interaction.user.id, Name="empty")
        db_session.add(pl)
        db_session.commit()

        playlist_cog.audio.play = AsyncMock()
        mock_interaction.user.voice = MagicMock()

        await MusicPlaylist.playlist._children["load"].callback(playlist_cog, mock_interaction, name="empty")

        playlist_cog.audio.play.assert_not_called()
        call_args = mock_interaction.followup.send.call_args
        assert "empty" in call_args.args[0].lower()
