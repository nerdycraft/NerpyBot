# -*- coding: utf-8 -*-
"""wow dbmodel"""

from sqlalchemy import BigInteger, Column, Index
from utils import database as db


class WoW(db.BASE):
    """Database entity model for World of Warcraft"""

    __tablename__ = "WoW"
    __table_args__ = (Index("WoW_GuildId", "GuildId"),)

    GuildId = Column(BigInteger, primary_key=True)
