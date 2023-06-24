# -*- coding: utf-8 -*-

from sqlalchemy import Column, BigInteger, String, Integer, Index, ForeignKeyConstraint
from sqlalchemy.orm import relationship

from models.RaidEncounter import RaidEncounter
from utils import database as db


class RaidEncounterRole(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounterRole"

    GuildId = Column(BigInteger, primary_key=True)
    TemplateId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String, primary_key=True)
    Icon = Column(String)
    Description = Column(String)
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
