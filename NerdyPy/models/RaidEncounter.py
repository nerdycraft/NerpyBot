from models.RaidTemplate import RaidTemplate
from utils import database as db
from sqlalchemy import BigInteger, Column, String, Index, ForeignKeyConstraint
from sqlalchemy.orm import relationship


class RaidEncounter(db.BASE):
    """database entity model for tags"""

    __tablename__ = "RaidEncounter"

    GuildId = Column(BigInteger, primary_key=True)
    RaidId = Column(BigInteger, primary_key=True)
    EncounterId = Column(BigInteger, primary_key=True)
    Name = Column(String)
    Description = Column(String)

    __table_args__ = (Index("RaidEncounter_GuildId_RaidId", "GuildId", "RaidId"),
                      ForeignKeyConstraint(
                          [GuildId, RaidId],
                          [RaidTemplate.GuildId, RaidTemplate.RaidId]
                      ))

    Roles = relationship(
        "RaidEncounterRole",
        back_populates="Encounter",
        cascade="all, delete, delete-orphan",
        lazy="joined",
        primaryjoin="and_(RaidEncounter.GuildId==RaidEncounterRole.GuildId, "
                    "RaidEncounter.RaidId==RaidEncounterRole.RaidId,"
                    "RaidEncounter.EncounterId==RaidEncounterRole.EncounterId)"
    )

    Raid = relationship("RaidTemplate", back_populates="Encounters",
                        primaryjoin="and_(RaidTemplate.GuildId==RaidEncounter.GuildId, "
                                    "RaidTemplate.RaidId==RaidEncounter.RaidId)")

    def get_total_participants(self):
        return sum(r.Count for r in self.Roles)

    def get_role_count(self):
        return len(self.Roles)

    def info(self):
        to_str = f'**{self.Name}** (🧑‍🤝‍🧑{self.get_total_participants()})\n\n'
        for role in self.Roles:
            to_str += f'{role}\n\n'
        return to_str
