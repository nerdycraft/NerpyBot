from models.RaidTemplate import RaidTemplate
from utils import database as db
from sqlalchemy import BigInteger, Column, String, Index, ForeignKeyConstraint
from sqlalchemy.orm import relationship


class RaidEncounter(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounter"

    GuildId = Column(BigInteger, primary_key=True)
    TemplateId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String)
    Description = Column(String)

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
