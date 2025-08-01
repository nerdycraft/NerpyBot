# -*- coding: utf-8 -*-
"""timed message database model"""

from datetime import UTC, datetime, timedelta

import humanize
from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text, asc
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
    ChannelName = Column(String(30))
    CreateDate = Column(DateTime)
    Author = Column(String(30))
    Repeat = Column(Integer)
    Minutes = Column(Integer)
    LastSend = Column(DateTime)
    Message = Column(Text)
    Count = Column(Integer)

    @classmethod
    def get_by_id(cls, timed_id, guild_id, session):
        """returns one message by id for given guild | session needed!"""
        return (
            session.query(ReminderMessage)
            .filter(ReminderMessage.Id == timed_id)
            .filter(ReminderMessage.GuildId == guild_id)
            .first()
        )

    @classmethod
    def get_all(cls, session):
        """returns all messages for all guilds | session needed!"""
        return session.query(ReminderMessage).order_by(asc("Id")).all()

    @classmethod
    def get_all_by_guild(cls, guild_id: int, session):
        """returns all messages for given guild | session needed!"""
        return session.query(ReminderMessage).filter(ReminderMessage.GuildId == guild_id).all()

    @classmethod
    def delete(cls, timed_id, guild_id: int, session):
        """deletes a message with id for given guild"""
        session.delete(ReminderMessage.get_by_id(timed_id, guild_id, session))

    def __str__(self):
        msg = f"==== {self.Id} ====\n\n"
        msg += f"Author: {self.Author}\n"
        msg += f"Channel: {self.ChannelName}\n"
        msg += f"Created: {self.CreateDate.strftime('%Y-%m-%d %H:%M')}\n"
        msg += (
            f"Next Message: "
            f"{humanize.naturaltime(self.LastSend + timedelta(minutes=float(self.Minutes)), when=datetime.now(UTC))}\n"
        )
        msg += f"Message: {self.Message}\n"
        msg += f"Hits: {self.Count}\n"
        return msg
