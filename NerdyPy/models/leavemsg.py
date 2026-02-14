# -*- coding: utf-8 -*-
"""Guild leave message configuration model"""

from sqlalchemy import BigInteger, Boolean, Column, Index, UnicodeText
from utils import database as db


class LeaveMessage(db.BASE):
    """Database entity model for guild leave messages"""

    __tablename__ = "LeaveMessage"
    __table_args__ = (Index("LeaveMessage_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    ChannelId = Column(BigInteger, nullable=True)
    Message = Column(UnicodeText, nullable=True)
    Enabled = Column(Boolean, default=False)

    @classmethod
    def get(cls, guild_id: int, session):
        """Returns the LeaveMessage entry for the given guild_id"""
        return session.query(LeaveMessage).filter(LeaveMessage.GuildId == guild_id).first()

    @classmethod
    def get_all_enabled(cls, session):
        """Returns all LeaveMessage entries where enabled"""
        return session.query(LeaveMessage).filter(LeaveMessage.Enabled.is_(True)).all()

    @classmethod
    def delete(cls, guild_id: int, session):
        """Deletes the LeaveMessage entry for the given guild_id"""
        leave_msg = LeaveMessage.get(guild_id, session)
        if leave_msg:
            session.delete(leave_msg)
