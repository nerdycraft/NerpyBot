# -*- coding: utf-8 -*-
"""Application submission, answer, and vote models, plus built-in template data."""

import enum

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, Unicode, UnicodeText
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship, selectinload
from utils import database as db

from models.application.forms import (
    ApplicationForm,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    BUILT_IN_TEMPLATES,
)


class SubmissionStatus(str, enum.Enum):
    """Valid status values for an application submission."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class VoteType(str, enum.Enum):
    """Valid vote types for a reviewer's vote on a submission."""

    APPROVE = "approve"
    DENY = "deny"


class ApplicationSubmission(db.BASE):
    """Database entity model for a user's submission to an application form."""

    __tablename__ = "ApplicationSubmission"
    __table_args__ = (
        Index("ApplicationSubmission_GuildId", "GuildId"),
        Index("ApplicationSubmission_FormId", "FormId"),
        Index("ApplicationSubmission_ReviewMessageId", "ReviewMessageId"),
    )

    Id = Column(Integer, primary_key=True)
    FormId = Column(Integer, ForeignKey("ApplicationForm.Id"), nullable=False)
    GuildId = Column(BigInteger, nullable=False)
    UserId = Column(BigInteger, nullable=False)
    UserName = Column(Unicode(50))
    Status = Column(SAEnum(SubmissionStatus), nullable=False, default=SubmissionStatus.PENDING)
    SubmittedAt = Column(DateTime, nullable=False)
    ReviewMessageId = Column(BigInteger, nullable=True)
    DecisionReason = Column(UnicodeText, nullable=True)
    ApplicantNotified = Column(Boolean, nullable=False, default=False, server_default="0")

    form = relationship("ApplicationForm", back_populates="submissions")
    answers = relationship(
        "ApplicationAnswer",
        back_populates="submission",
        cascade="all, delete, delete-orphan",
        lazy="joined",
    )
    votes = relationship(
        "ApplicationVote",
        back_populates="submission",
        cascade="all, delete, delete-orphan",
        lazy="select",
    )

    @classmethod
    def get_by_id(cls, submission_id, session):
        """Returns a submission by its primary key, with votes eager-loaded."""
        return session.query(cls).options(selectinload(cls.votes)).filter(cls.Id == submission_id).first()

    @classmethod
    def get_by_review_message(cls, message_id, session):
        """Returns a submission by its review message ID, with votes eager-loaded."""
        return session.query(cls).options(selectinload(cls.votes)).filter(cls.ReviewMessageId == message_id).first()

    @classmethod
    def get_by_guild(cls, guild_id, session):
        """Returns all submissions for a guild, with form and votes eager-loaded."""
        return (
            session.query(cls)
            .options(selectinload(cls.form).lazyload(ApplicationForm.questions), selectinload(cls.votes))
            .filter(cls.GuildId == guild_id)
            .all()
        )

    @classmethod
    def get_by_user_and_form(cls, user_id: int, form_id: int, session):
        """Returns the most recent submission by a user for a given form, or None."""
        return session.query(cls).filter(cls.UserId == user_id, cls.FormId == form_id).order_by(cls.Id.desc()).first()


class ApplicationAnswer(db.BASE):
    """Database entity model for an answer to a question in a submission."""

    __tablename__ = "ApplicationAnswer"
    __table_args__ = (
        Index("ApplicationAnswer_SubmissionId", "SubmissionId"),
        Index("ApplicationAnswer_SubmissionId_QuestionId", "SubmissionId", "QuestionId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    SubmissionId = Column(Integer, ForeignKey("ApplicationSubmission.Id"), nullable=False)
    QuestionId = Column(Integer, ForeignKey("ApplicationQuestion.Id"), nullable=False)
    AnswerText = Column(UnicodeText, nullable=False)

    submission = relationship("ApplicationSubmission", back_populates="answers")
    question = relationship("ApplicationQuestion", lazy="joined")


class ApplicationVote(db.BASE):
    """Database entity model for a reviewer's vote on a submission."""

    __tablename__ = "ApplicationVote"
    __table_args__ = (
        Index("ApplicationVote_SubmissionId", "SubmissionId"),
        Index("ApplicationVote_SubmissionId_UserId", "SubmissionId", "UserId", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    SubmissionId = Column(Integer, ForeignKey("ApplicationSubmission.Id"), nullable=False)
    UserId = Column(BigInteger, nullable=False)
    VoterName = Column(Unicode(100), nullable=True)
    Vote = Column(SAEnum(VoteType), nullable=False)

    submission = relationship("ApplicationSubmission", back_populates="votes")

    @classmethod
    def get_by_submission(cls, submission_id, session):
        """Returns all votes for a submission."""
        return session.query(cls).filter(cls.SubmissionId == submission_id).all()

    @classmethod
    def get_user_vote(cls, submission_id, user_id, session):
        """Returns a specific user's vote on a submission."""
        return session.query(cls).filter(cls.SubmissionId == submission_id, cls.UserId == user_id).first()

    @classmethod
    def count_by_type(cls, submission_id, vote_type, session):
        """Returns the count of votes of a given type for a submission."""
        return session.query(cls).filter(cls.SubmissionId == submission_id, cls.Vote == vote_type).count()


def seed_built_in_templates(session):
    """Seed built-in templates into DB if not already present, and remove stale ones."""
    existing_templates = session.query(ApplicationTemplate).filter(ApplicationTemplate.IsBuiltIn.is_(True)).all()
    existing_names = {tpl.Name for tpl in existing_templates}

    # Remove built-in templates no longer in the current dict
    for tpl in existing_templates:
        if tpl.Name not in BUILT_IN_TEMPLATES:
            session.delete(tpl)

    # Seed missing templates
    for name, questions in BUILT_IN_TEMPLATES.items():
        if name in existing_names:
            continue
        template = ApplicationTemplate(Name=name, GuildId=None, IsBuiltIn=True)
        session.add(template)
        session.flush()
        for i, q_text in enumerate(questions, start=1):
            session.add(ApplicationTemplateQuestion(TemplateId=template.Id, QuestionText=q_text, SortOrder=i))
