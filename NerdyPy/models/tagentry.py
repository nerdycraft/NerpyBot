""" tag entry database model """
# -*- coding: utf-8 -*-

from utils import database as db
from sqlalchemy.orm import relationship
from sqlalchemy import Integer, Column, ForeignKey, LargeBinary, String, Index


class TagEntry(db.BASE):
    """Database Entity Model for tag entries"""

    __tablename__ = "TagEntry"
    __table_args__ = (Index("TagEntry_TagId", "TagId"),)

    Id = Column(Integer, primary_key=True)
    TagId = Column(Integer, ForeignKey("Tag.Id"))
    TextContent = Column(String(255))
    ByteContent = Column(LargeBinary(16777215))

    tag = relationship("Tag", back_populates="entries")
