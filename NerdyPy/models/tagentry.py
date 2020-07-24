""" tag entry database model """
# -*- coding: utf-8 -*-
from utils.database import BASE
from sqlalchemy.orm import relationship
from sqlalchemy import BigInteger, Column, ForeignKey, LargeBinary, String


class TagEntry(BASE):
    """Database Entity Model for tag entries"""

    __tablename__ = "TagEntry"

    Id = Column(BigInteger, primary_key=True)
    TagId = Column(BigInteger, ForeignKey("Tag.Id"))
    TextContent = Column(String)
    ByteContent = Column(LargeBinary)

    tag = relationship("Tag", back_populates="entries")
