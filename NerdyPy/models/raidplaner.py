# -*- coding: utf-8 -*-

from discord import Embed
from sqlalchemy import BigInteger, Column, String, Index, ForeignKeyConstraint, Integer, DateTime, asc
from sqlalchemy.orm import relationship

from utils import database as db


class RaidTemplate(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidTemplate"
    __table_args__ = (Index("RaidTemplate_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    TemplateId = Column(BigInteger, primary_key=True)
    Name = Column(String(30))
    Description = Column(String(255))
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
        emb = Embed(title=self.Name, description=f"{self.Description}\n🧑‍🤝‍🧑 {self.PlayerCount}\n\n")

        for enc in self.Encounters:
            emb.description += str(enc)

        return emb


class RaidEncounter(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounter"

    GuildId = Column(BigInteger, primary_key=True)
    TemplateId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String(30))
    Description = Column(String(255))

    __table_args__ = (
        Index("RaidEncounter_GuildId_TemplateId", "GuildId", "TemplateId"),
        ForeignKeyConstraint([GuildId, TemplateId], [RaidTemplate.GuildId, RaidTemplate.TemplateId]),
    )

    Roles = relationship(
        "RaidEncounterRole",
        back_populates="Encounter",
        cascade="all, delete, delete-orphan",
        lazy="joined",
        primaryjoin="and_(RaidEncounter.GuildId==RaidEncounterRole.GuildId, "
        "RaidEncounter.TemplateId==RaidEncounterRole.TemplateId,"
        "RaidEncounter.EncounterId==RaidEncounterRole.EncounterId)",
    )

    Raid = relationship(
        "RaidTemplate",
        back_populates="Encounters",
        primaryjoin="and_(RaidTemplate.GuildId==RaidEncounter.GuildId, "
        "RaidTemplate.TemplateId==RaidEncounter.TemplateId)",
    )

    def get_role_player_sum(self):
        return sum(r.Count for r in self.Roles)

    def get_role_count(self):
        return len(self.Roles)

    def info(self):
        to_str = f"**{self.Name}**\n\n"
        for role in self.Roles:
            to_str += f"{role}\n\n"
        return to_str


class RaidEncounterRole(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounterRole"

    GuildId = Column(BigInteger, primary_key=True)
    TemplateId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String(30), primary_key=True)
    Icon = Column(String(30))
    Description = Column(String(255))
    Count = Column(Integer)
    SortIndex = Column(Integer)

    __table_args__ = (
        Index("RaidEncounterRole_GuildId_TemplateId_EncounterId", "GuildId", "TemplateId", "EncounterId"),
        ForeignKeyConstraint(
            [GuildId, TemplateId, EncounterId],
            [RaidEncounter.GuildId, RaidEncounter.TemplateId, RaidEncounter.EncounterId],
        ),
    )

    Encounter = relationship(
        "RaidEncounter",
        back_populates="Roles",
        primaryjoin="and_(RaidEncounter.GuildId==RaidEncounterRole.GuildId, "
        "RaidEncounter.TemplateId==RaidEncounterRole.TemplateId,"
        "RaidEncounter.EncounterId==RaidEncounterRole.EncounterId)",
    )

    def __str__(self):
        return f"{self.Icon} ***{self.Name}*** ({self.Count})\n{self.Description}"


class RaidEvent(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEvent"
    __table_args__ = (Index("RaidEvent_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
    RaidId = Column(BigInteger, primary_key=True)
    Name = Column(String(30))
    Description = Column(String(255))
    StartDate = Column(DateTime)
    EndDate = Column(DateTime)
    Organizer = Column(String(30))
    PlayerCount = Column(Integer)
    CreateDate = Column(DateTime)
    MessageRef = Column(String(255))

    @classmethod
    def get_from_guild(cls, guild_id: int, session):
        """returns all templates for given guild"""
        return session.query(RaidEvent).filter(RaidEvent.GuildId == guild_id).order_by(asc("CreateDate")).all()

    def get_encounter_count(self):
        return len(self.Encounters)

    def create_info_embed(self):
        emb = Embed(title=self.Name, description=f"{self.Description}\n🧑‍🤝‍🧑 {self.PlayerCount}\n\n")

        for enc in self.Encounters:
            emb.description += str(enc)

        return emb
