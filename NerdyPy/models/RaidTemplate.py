""" Raid DB Model """
# -*- coding: utf-8 -*-

from utils import database as db
from sqlalchemy.orm import relationship
from sqlalchemy import BigInteger, Column, Integer, String, Index


class RaidEncounterRole(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounterRole"
    __table_args__ = (Index("RaidEncounterRole_GuildId_RaidId_EncounterId", "GuildId", "RaidId", "EncounterId"))

    GuildId = Column(BigInteger, primary_key=True)
    RaidId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String, primary_key=True)
    Icon = Column(String)
    Description = Column(String)
    Count = Column(Integer)
    SortIndex = Column(Integer)

    Encounter = relationship("RaidEncounter", back_populates="Roles")


class RaidEncounter(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounter"
    __table_args__ = (Index("RaidEncounter_GuildId_RaidId", "GuildId", "RaidId"))

    GuildId = Column(BigInteger, primary_key=True)
    RaidId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String)
    Description = Column(String)

    Roles = relationship(
        "RaidEncounterRole",
        back_populates="Encounter",
        cascade="all, delete, delete-orphan",
        lazy="dynamic",
    )

    Raid = relationship("Raid", back_populates="Encounters")


class Raid(db.BASE):
    """database entity model for tags"""

    __tablename__ = "Raid"
    __table_args__ = (Index("Raid_GuildId", "GuildId"))

    GuildId = Column(BigInteger, primary_key=True)
    RaidId = Column(BigInteger, primary_key=True)
    Name = Column(String)
    Description = Column(String)

    Encounters = relationship(
        "RaidEncounter",
        back_populates="tag",
        cascade="all, delete, delete-orphan",
        lazy="dynamic",
    )
