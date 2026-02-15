# -*- coding: utf-8 -*-
"""Reaction Role database models"""

from sqlalchemy import BigInteger, Column, ForeignKey, Index, Integer, Unicode
from sqlalchemy.orm import relationship
from utils import database as db


class ReactionRoleMessage(db.BASE):
    """Database entity for a message that grants roles via reactions"""

    __tablename__ = "ReactionRoleMessage"
    __table_args__ = (Index("ReactionRoleMessage_GuildId", "GuildId"),)

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    ChannelId = Column(BigInteger)
    MessageId = Column(BigInteger, unique=True)

    entries = relationship(
        "ReactionRoleEntry",
        back_populates="message",
        cascade="all, delete, delete-orphan",
        lazy="joined",
    )

    @classmethod
    def get_by_message(cls, message_id, session):
        """returns a reaction role message by Discord message ID | session needed!"""
        return session.query(cls).filter(cls.MessageId == message_id).first()

    @classmethod
    def get_by_guild(cls, guild_id, session):
        """returns all reaction role messages for a guild | session needed!"""
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def delete(cls, message_id, session):
        """deletes a reaction role message by Discord message ID"""
        msg = cls.get_by_message(message_id, session)
        if msg:
            session.delete(msg)


class ReactionRoleEntry(db.BASE):
    """Database entity mapping an emoji to a role on a reaction role message"""

    __tablename__ = "ReactionRoleEntry"
    __table_args__ = (Index("ReactionRoleEntry_MessageId", "ReactionRoleMessageId"),)

    Id = Column(Integer, primary_key=True)
    ReactionRoleMessageId = Column(Integer, ForeignKey("ReactionRoleMessage.Id"))
    Emoji = Column(Unicode(100))
    RoleId = Column(BigInteger)

    message = relationship("ReactionRoleMessage", back_populates="entries")

    @classmethod
    def get_by_message_and_emoji(cls, message_id, emoji, session):
        """returns an entry matching a ReactionRoleMessage ID and emoji | session needed!"""
        return session.query(cls).filter(cls.ReactionRoleMessageId == message_id).filter(cls.Emoji == emoji).first()
