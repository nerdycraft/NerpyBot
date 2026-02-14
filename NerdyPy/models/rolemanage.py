# -*- coding: utf-8 -*-
"""Role management delegation database models"""

from sqlalchemy import BigInteger, Column, Index, Integer, UniqueConstraint
from utils import database as db


class RoleMapping(db.BASE):
    """Database entity mapping a source role to a target role it can assign"""

    __tablename__ = "RoleMapping"
    __table_args__ = (
        Index("RoleMapping_GuildId", "GuildId"),
        UniqueConstraint("GuildId", "SourceRoleId", "TargetRoleId", name="uq_guild_source_target"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger)
    SourceRoleId = Column(BigInteger)
    TargetRoleId = Column(BigInteger)

    @classmethod
    def get_by_guild(cls, guild_id, session):
        """returns all role mappings for a guild | session needed!"""
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def get(cls, guild_id, source_role_id, target_role_id, session):
        """returns a specific mapping | session needed!"""
        return (
            session.query(cls)
            .filter(cls.GuildId == guild_id, cls.SourceRoleId == source_role_id, cls.TargetRoleId == target_role_id)
            .first()
        )

    @classmethod
    def get_by_target(cls, guild_id, target_role_id, session):
        """returns all mappings for a given target role | session needed!"""
        return session.query(cls).filter(cls.GuildId == guild_id, cls.TargetRoleId == target_role_id).all()

    @classmethod
    def delete(cls, guild_id, source_role_id, target_role_id, session):
        """deletes a specific mapping"""
        mapping = cls.get(guild_id, source_role_id, target_role_id, session)
        if mapping:
            session.delete(mapping)
            return True
        return False
