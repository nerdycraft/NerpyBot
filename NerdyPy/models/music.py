# -*- coding: utf-8 -*-
"""Playlist and PlaylistEntry models for the music module."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, UniqueConstraint, Unicode, UnicodeText

from utils import database as db


class Playlist(db.BASE):
    __tablename__ = "MusicPlaylist"
    __table_args__ = (
        Index("MusicPlaylist_GuildId_UserId", "GuildId", "UserId"),
        UniqueConstraint("GuildId", "UserId", "Name", name="uq_playlist_guild_user_name"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger, nullable=False)
    UserId = Column(BigInteger, nullable=False)
    Name = Column(Unicode(100), nullable=False)
    CreatedAt = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None))

    @classmethod
    def get_by_user(cls, guild_id: int, user_id: int, session):
        return session.query(cls).filter(cls.GuildId == guild_id, cls.UserId == user_id).all()

    @classmethod
    def get_by_name(cls, guild_id: int, user_id: int, name: str, session):
        return session.query(cls).filter(cls.GuildId == guild_id, cls.UserId == user_id, cls.Name == name).first()


class PlaylistEntry(db.BASE):
    __tablename__ = "MusicPlaylistEntry"
    __table_args__ = (Index("MusicPlaylistEntry_PlaylistId", "PlaylistId"),)

    Id = Column(Integer, primary_key=True)
    PlaylistId = Column(Integer, ForeignKey("MusicPlaylist.Id", ondelete="CASCADE"), nullable=False)
    Url = Column(UnicodeText, nullable=False)
    Title = Column(Unicode(200), nullable=False)
    Position = Column(Integer, nullable=False, default=0)

    @classmethod
    def get_by_playlist(cls, playlist_id: int, session):
        return session.query(cls).filter(cls.PlaylistId == playlist_id).order_by(cls.Position).all()

    @classmethod
    def delete_by_url(cls, playlist_id: int, url: str, session) -> int:
        """Delete entries matching url. Returns the number of rows deleted."""
        return session.query(cls).filter(cls.PlaylistId == playlist_id, cls.Url == url).delete()
