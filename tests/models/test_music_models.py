# -*- coding: utf-8 -*-
"""Tests for Playlist and PlaylistEntry models."""

import pytest
from models.music import Playlist, PlaylistEntry


class TestPlaylist:
    def test_create_playlist(self, db_session):
        p = Playlist(GuildId=1, UserId=2, Name="chill vibes")
        db_session.add(p)
        db_session.commit()
        assert p.Id is not None

    def test_get_by_user(self, db_session):
        db_session.add(Playlist(GuildId=1, UserId=2, Name="A"))
        db_session.add(Playlist(GuildId=1, UserId=2, Name="B"))
        db_session.add(Playlist(GuildId=1, UserId=99, Name="other"))
        db_session.commit()
        results = Playlist.get_by_user(1, 2, db_session)
        assert len(results) == 2
        assert all(p.UserId == 2 for p in results)

    def test_get_by_name(self, db_session):
        db_session.add(Playlist(GuildId=1, UserId=2, Name="chill"))
        db_session.commit()
        p = Playlist.get_by_name(1, 2, "chill", db_session)
        assert p is not None
        assert p.Name == "chill"

    def test_get_by_name_not_found(self, db_session):
        result = Playlist.get_by_name(1, 2, "missing", db_session)
        assert result is None

    def test_name_unique_per_user_guild(self, db_session):
        from sqlalchemy.exc import IntegrityError

        db_session.add(Playlist(GuildId=1, UserId=2, Name="dupe"))
        db_session.commit()
        db_session.add(Playlist(GuildId=1, UserId=2, Name="dupe"))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPlaylistEntry:
    def test_add_entry(self, db_session):
        p = Playlist(GuildId=1, UserId=2, Name="test")
        db_session.add(p)
        db_session.flush()
        e = PlaylistEntry(PlaylistId=p.Id, Url="https://youtube.com/1", Title="Song", Position=0)
        db_session.add(e)
        db_session.commit()
        assert e.Id is not None

    def test_get_entries_ordered(self, db_session):
        p = Playlist(GuildId=1, UserId=2, Name="ordered")
        db_session.add(p)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=p.Id, Url="u2", Title="B", Position=1))
        db_session.add(PlaylistEntry(PlaylistId=p.Id, Url="u1", Title="A", Position=0))
        db_session.commit()
        entries = PlaylistEntry.get_by_playlist(p.Id, db_session)
        assert [e.Title for e in entries] == ["A", "B"]

    def test_delete_entry_by_url(self, db_session):
        p = Playlist(GuildId=1, UserId=2, Name="del")
        db_session.add(p)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=p.Id, Url="https://yt/1", Title="X", Position=0))
        db_session.commit()
        deleted = PlaylistEntry.delete_by_url(p.Id, "https://yt/1", db_session)
        db_session.commit()
        assert deleted == 1
        assert PlaylistEntry.get_by_playlist(p.Id, db_session) == []

    def test_delete_entry_by_url_missing_returns_zero(self, db_session):
        p = Playlist(GuildId=1, UserId=2, Name="nomatch")
        db_session.add(p)
        db_session.flush()
        db_session.commit()
        deleted = PlaylistEntry.delete_by_url(p.Id, "https://yt/nonexistent", db_session)
        assert deleted == 0

    def test_cascade_delete_playlist_removes_entries(self, db_session):
        """DB-level CASCADE: deleting a Playlist bulk-deletes its entries."""
        p = Playlist(GuildId=1, UserId=2, Name="cascade-test")
        db_session.add(p)
        db_session.flush()
        playlist_id = p.Id
        db_session.add(PlaylistEntry(PlaylistId=playlist_id, Url="https://yt/a", Title="A", Position=0))
        db_session.add(PlaylistEntry(PlaylistId=playlist_id, Url="https://yt/b", Title="B", Position=1))
        db_session.commit()

        db_session.query(Playlist).filter(Playlist.Id == playlist_id).delete(synchronize_session="fetch")
        db_session.commit()

        assert PlaylistEntry.get_by_playlist(playlist_id, db_session) == []
