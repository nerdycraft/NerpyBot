""" uhm """
# -*- coding: utf-8 -*-

import asyncio
from enum import Enum
from models.tagentry import TagEntry
from utils.errors import NerpyException
from sqlalchemy.orm import relationship
from discord.ext.commands import Converter
from utils import database as db
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, asc


class Tag(db.BASE):
    """database entity model for tags"""
    __tablename__ = "Tag"

    Id = Column(BigInteger, primary_key=True)
    GuildId = Column(BigInteger)
    Name = Column(String)
    Type = Column(Integer)
    Author = Column(String)
    CreateDate = Column(DateTime)
    Count = Column(Integer)
    Volume = Column(Integer)

    entries = relationship("TagEntry", back_populates='tag',
                           cascade="all, delete, delete-orphan", lazy='dynamic')

    @classmethod
    def exists(cls, name, guild_id: int):
        """ checks the database if a tag with that name exists for that guild"""
        with db.session_scope() as session:
            count = session.query(Tag).filter(Tag.Name == name).filter(Tag.GuildId == guild_id).count()
        return True if count > 0 else False

    @classmethod
    def get(cls, name, guild_id, session):
        """returns a tag with given name for given guild | session needed!"""
        return session.query(Tag).filter(Tag.Name == name).filter(Tag.GuildId == guild_id).first()

    @classmethod
    def get_all_from_guild(cls, guild_id: int, session):
        """returns all tags for given guild | session needed!"""
        return session.query(Tag).filter(Tag.GuildId == guild_id).order_by(asc('Name')).all()

    @classmethod
    def delete(cls, name, guild_id: int):
        """deletes a tag with given name for given guild"""
        with db.session_scope() as session:
            session.delete(Tag.get(name, guild_id, session))

    @classmethod
    def add(cls, tag, session):
        """add a tag with given name for given guild"""
        session.add(tag)

    def add_entry(self, text: str, session, byt: bytes = None):
        """add a tag entry with given name for given guild"""
        session.add(TagEntry(TagId=self.Id, TextContent=text, ByteContent=byt))

    def __str__(self):
        msg = f"==== {self.Name} ====\n\n"
        msg += f'Author: {self.Author}\n'
        msg += f'Type: {TagType(self.Type).name}\n'
        msg += f'Created: {self.CreateDate.strftime("%Y-%m-%d %H:%M")}\n'
        msg += f'Hits: {self.Count}\n'
        msg += f'Entries: {self.entries.count()}'
        return msg


class TagConverter(Converter):

    @asyncio.coroutine
    def convert(self, ctx, argument):
        with db.session_scope() as session:
            _tag = Tag.get(argument, ctx.guild.id, session)
        return _tag


class TagType(Enum):
    """enum to define tags type"""
    sound = 0
    text = 1
    url = 2


class TagTypeConverter(Converter):

    @asyncio.coroutine
    def convert(self, ctx, argument):
        low = argument.lower()
        try:
            return TagType[low].value
        except KeyError:
            raise NerpyException(f'TagType {argument} was not found.')
