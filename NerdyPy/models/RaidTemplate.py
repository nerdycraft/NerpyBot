""" Raid DB Model """
# -*- coding: utf-8 -*-
from discord import Embed

from utils import database as db
from sqlalchemy.orm import relationship
from sqlalchemy import BigInteger, Column, String, Index, DateTime, asc, Integer


class RaidTemplate(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidTemplate"
    __table_args__ = (Index("RaidTemplate_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    TemplateId = Column(BigInteger, primary_key=True)
    Name = Column(String)
    Description = Column(String)
    PlayerCount = Column(Integer)
    CreateDate = Column(DateTime)

    Encounters = relationship(
        "RaidEncounter",
        back_populates="Raid",
        cascade="all, delete, delete-orphan",
        lazy="joined",
        primaryjoin="and_(RaidTemplate.GuildId==RaidEncounter.GuildId, "
        "RaidTemplate.TemplateId==RaidEncounter.TemplateId) ",
    )

    @classmethod
    def get_from_guild(cls, guild_id: int, session):
        """returns all templates for given guild"""
        return session.query(RaidTemplate).filter(RaidTemplate.GuildId == guild_id).order_by(asc("CreateDate")).all()

    def get_encounter_count(self):
        return len(self.Encounters)

    def create_info_embed(self):
        emb = Embed(title=self.Name, description=f"{self.Description}\n" f"🧑‍🤝‍🧑 {self.PlayerCount}\n\n")

        for enc in self.Encounters:
            emb.description += str(enc)

        return emb
