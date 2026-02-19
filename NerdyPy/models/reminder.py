# NerdyPy/models/reminder.py
# -*- coding: utf-8 -*-
"""Timed message database model (rewritten for absolute timestamps + calendar scheduling)."""

from datetime import UTC, datetime

import humanize
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Time, Unicode, UnicodeText, func
from utils import database as db


class ReminderMessage(db.BASE):
    """Database entity model for timed/scheduled messages."""

    __tablename__ = "ReminderMessage"
    __table_args__ = (
        Index("ReminderMessage_GuildId", "GuildId"),
        Index("ReminderMessage_Id_GuildId", "Id", "GuildId", unique=True),
        Index("ReminderMessage_NextFire_Enabled", "NextFire", "Enabled"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    ChannelName = Column(String(30))
    CreateDate = Column(DateTime, nullable=False)
    Author = Column(Unicode(30))
    Message = Column(UnicodeText)
    Enabled = Column(Boolean, default=True)
    Count = Column(Integer, default=0)

    # Scheduling
    NextFire = Column(DateTime, nullable=False)
    ScheduleType = Column(String(10), nullable=False)  # interval, daily, weekly, monthly, once
    IntervalSeconds = Column(Integer, nullable=True)
    ScheduleTime = Column(Time, nullable=True)
    ScheduleDayOfWeek = Column(Integer, nullable=True)  # 0=Monday .. 6=Sunday
    ScheduleDayOfMonth = Column(Integer, nullable=True)  # 1-28
    Timezone = Column(String(50), nullable=True)  # IANA timezone string, None = UTC

    @classmethod
    def get_by_id(cls, reminder_id, guild_id, session):
        return session.query(cls).filter(cls.Id == reminder_id, cls.GuildId == guild_id).first()

    @classmethod
    def get_all_by_guild(cls, guild_id: int, session):
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def get_due(cls, session):
        """Return all enabled reminders whose NextFire is in the past."""
        now = datetime.now(UTC)
        return session.query(cls).filter(cls.Enabled.is_(True), cls.NextFire <= now).all()

    @classmethod
    def get_next_fire_time(cls, session) -> datetime | None:
        """Return the earliest NextFire among enabled reminders, or None."""
        result = session.query(func.min(cls.NextFire)).filter(cls.Enabled.is_(True)).scalar()
        if result is not None:
            return result.replace(tzinfo=UTC)
        return None

    @classmethod
    def delete(cls, reminder_id, guild_id: int, session):
        obj = cls.get_by_id(reminder_id, guild_id, session)
        if obj is None:
            return
        session.delete(obj)

    def __str__(self):
        next_str = humanize.naturaltime(self.NextFire.replace(tzinfo=UTC), when=datetime.now(UTC))
        msg = f"==== {self.Id} ====\n\n"
        msg += f"Author: {self.Author}\n"
        msg += f"Channel: {self.ChannelName}\n"
        msg += f"Created: {self.CreateDate.strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"Type: {self.ScheduleType}\n"
        msg += f"Next: {next_str}\n"
        msg += f"Message: {self.Message}\n"
        msg += f"Hits: {self.Count}\n"
        return msg
