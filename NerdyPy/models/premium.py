# -*- coding: utf-8 -*-
"""Premium-domain database models: dashboard premium access grants."""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Column, DateTime

from utils import database as db


class PremiumUser(db.BASE):
    """Dashboard users who have been granted premium access by an operator."""

    __tablename__ = "PremiumUser"
    UserId = Column(BigInteger, primary_key=True)
    GrantedAt = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    GrantedByUserId = Column(BigInteger, nullable=True)

    @classmethod
    def has(cls, user_id: int, session) -> bool:
        """Return True if the user has premium dashboard access."""
        return session.query(cls).filter(cls.UserId == user_id).first() is not None

    @classmethod
    def get_all(cls, session) -> list["PremiumUser"]:
        """Return all premium users ordered by grant date."""
        return session.query(cls).order_by(cls.GrantedAt).all()

    @classmethod
    def grant(cls, user_id: int, granted_by: int, session) -> "PremiumUser":
        """Grant premium to a user idempotently. Returns the existing entry if already present."""
        from sqlalchemy.exc import IntegrityError

        entry = cls(UserId=user_id, GrantedByUserId=granted_by)
        try:
            with session.begin_nested():
                session.add(entry)
                session.flush()
        except IntegrityError:
            return session.query(cls).filter(cls.UserId == user_id).first()
        return entry

    @classmethod
    def revoke(cls, user_id: int, session) -> bool:
        """Revoke premium from a user. Returns True if the entry existed."""
        entry = session.query(cls).filter(cls.UserId == user_id).first()
        if entry:
            session.delete(entry)
            return True
        return False
