# -*- coding: utf-8 -*-
"""Tests for Playlist and PlaylistEntry models."""

from models.music import Playlist, PlaylistEntry


class TestPlaylist:
    def test_get_by_user(self, db_session):
        db_session.add(Playlist(GuildId=1, UserId=2, Name="A"))
        db_session.add(Playlist(GuildId=1, UserId=2, Name="B"))
        db_session.add(Playlist(GuildId=1, UserId=99, Name="other"))
        db_session.commit()
        results = Playlist.get_by_user(1, 2, db_session)
        assert len(results) == 2
        assert all(p.UserId == 2 for p in results)


class TestPlaylistEntry:
    def test_get_entries_ordered(self, db_session):
        p = Playlist(GuildId=1, UserId=2, Name="ordered")
        db_session.add(p)
        db_session.flush()
        db_session.add(PlaylistEntry(PlaylistId=p.Id, Url="u2", Title="B", Position=1))
        db_session.add(PlaylistEntry(PlaylistId=p.Id, Url="u1", Title="A", Position=0))
        db_session.commit()
        entries = PlaylistEntry.get_by_playlist(p.Id, db_session)
        assert [e.Title for e in entries] == ["A", "B"]
