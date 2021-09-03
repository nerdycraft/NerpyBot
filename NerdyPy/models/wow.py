""" uhm """
# -*- coding: utf-8 -*-

from utils import database as db
from sqlalchemy import Integer, BigInteger, SmallInteger, Column, DateTime, String, Index, inspect


class WoW(db.BASE):
    """database entity model for wow mplus keys"""

    __tablename__ = "WoW"
    __table_args__ = (
        Index("WoW_GuildId", "GuildId"),
        Index("WoW_Character_GuildId", "Character", "GuildId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    KeystoneName = Column(String)
    KeystoneLevel = Column(SmallInteger)
    Character = Column(String)
    CreateDate = Column(DateTime)
    ModifiedDate = Column(DateTime)
    Author = Column(String)

    @classmethod
    def object_as_dict(cls, obj):
        return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

    @classmethod
    def exists(cls, guild_id: int, character, session):
        """checks if a character already has a key for this guild"""
        count = session.query(WoW).filter(WoW.GuildId == guild_id).filter(WoW.Character == character).count()

        return True if count > 0 else False

    @classmethod
    def get_keystones(cls, guild_id: int, session):
        """returns all keystones for guild"""
        keystones = []
        result = session.query(WoW).filter(WoW.GuildId == guild_id).all()

        for key in result:
            keystones.append(cls.object_as_dict(key))

        return keystones

    @classmethod
    def get_keystone_by_author(cls, guild_id: int, author, session):
        """returns all keystones added by a specific user"""
        keystones = []
        result = session.query(WoW).filter(WoW.GuildId == guild_id).filter(WoW.Author == author).all()

        for key in result:
            keystones.append(cls.object_as_dict(key))

        return keystones

    @classmethod
    def get_keystone_by_level(cls, guild_id: int, keystone_level, session):
        """returns all keystone with a specific level"""
        keystones = []
        result = session.query(WoW).filter(WoW.GuildId == guild_id).filter(WoW.KeystoneLevel == keystone_level).all()

        for key in result:
            keystones.append(cls.object_as_dict(key))

        return keystones

    @classmethod
    def get_keystone_by_name(cls, guild_id: int, keystone_name, session):
        """return all keystones by name"""
        keystones = []
        result = session.query(WoW).filter(WoW.GuildId == guild_id).filter(WoW.KeystoneName == keystone_name).all()

        for key in result:
            keystones.append(cls.object_as_dict(key))

        return keystones

    @classmethod
    def get_keystone_by_character(cls, guild_id: int, character, session):
        """return all keystones for a given character"""
        keystones = []
        result = session.query(WoW).filter(WoW.GuildId == guild_id).filter(WoW.Character == character).all()

        for key in result:
            keystones.append(cls.object_as_dict(key))

        return keystones

    @classmethod
    def delete(cls, guild_id: int, character, session):
        """deletes a keystone for character in given guild"""
        objects = session.query(WoW).filter(WoW.GuildId == guild_id).filter(WoW.Character == character)
        for o in objects:
            session.delete(o)
        session.flush()

    @classmethod
    def add(cls, guild_id: int, keystone_name: str, keystone_level: str, character: str, createdate, author, session):
        keystone = WoW(
            GuildId=guild_id,
            KeystoneName=keystone_name,
            KeystoneLevel=keystone_level,
            Character=character,
            CreateDate=createdate,
            Author=author,
        )
        session.add(keystone)
        session.flush()
