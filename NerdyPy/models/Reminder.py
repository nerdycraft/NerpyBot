# -*- coding: utf-8 -*-
""" timed message database model """

from datetime import timedelta

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Index, asc

from utils import database as db


class ReminderMessage(db.BASE):
    """database entity model for timed message"""

    __tablename__ = "ReminderMessage"
    __table_args__ = (
        Index("ReminderMessage_GuildId", "GuildId"),
        Index("ReminderMessage_Id_GuildId", "Id", "GuildId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    CreateDate = Column(DateTime)
    Author = Column(String(30))
    Repeat = Column(Integer)
    Minutes = Column(Integer)
    LastSend = Column(DateTime)
    Message = Column(String(30))
    Count = Column(Integer)

    @classmethod
    def get(cls, timed_id, guild_id, session):
        """returns a tag with given name for given guild | session needed!"""
        return (
            session.query(ReminderMessage)
            .filter(ReminderMessage.Id == timed_id)
            .filter(ReminderMessage.GuildId == guild_id)
            .first()
        )

    @classmethod
    def get_all(cls, session):
        """returns all tags for given guild | session needed!"""
        return session.query(ReminderMessage).order_by(asc("Id")).all()

    @classmethod
    def get_all_by_guild(cls, guild_id: int, session):
        """returns all tags for given guild | session needed!"""
        return session.query(ReminderMessage).filter(ReminderMessage.GuildId == guild_id).all()

    @classmethod
    def delete(cls, timed_id, guild_id: int, session):
        """deletes a tag with given name for given guild"""
        session.delete(ReminderMessage.get(timed_id, guild_id, session))

    def __str__(self):
        msg = f"==== {self.Id} ====\n\n"
        msg += f"Author: {self.Author}\n"
        msg += f"Created: {self.CreateDate.strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"Next Message: {(self.LastSend + timedelta(minutes=self.Minutes.float())).strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"Message: {self.Message}\n"
        msg += f"Hits: {self.Count}\n"
        return msg
