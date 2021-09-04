""" Raid DB Model """
# -*- coding: utf-8 -*-
from discord import Embed

from utils import database as db
from sqlalchemy import BigInteger, Column, String, Index, DateTime, asc, Integer


class RaidEvent(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEvent"
    __table_args__ = (Index("RaidEvent_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    RaidId = Column(BigInteger, primary_key=True)
    Name = Column(String)
    Description = Column(String)
    StartDate = Column(DateTime)
    EndDate = Column(DateTime)
    Organizer = Column(String)
    PlayerCount = Column(Integer)
    CreateDate = Column(DateTime)
    MessageRef = Column(String)

    @classmethod
    def get_from_guild(cls, guild_id: int, session):
        """returns all templates for given guild"""
        return session.query(RaidEvent).filter(RaidEvent.GuildId == guild_id).order_by(asc("CreateDate")).all()

    def get_encounter_count(self):
        return len(self.Encounters)

    def create_info_embed(self):
        emb = Embed(title=self.Name,
                    description=f'{self.Description}\n'
                                f'🧑‍🤝‍🧑 {self.PlayerCount}\n\n'
                    )

        for enc in self.Encounters:
            emb.description += str(enc)

        return emb
