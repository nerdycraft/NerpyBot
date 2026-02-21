# -*- coding: utf-8 -*-
"""Application form database models"""

import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Unicode,
    UnicodeText,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship
from utils import database as db


class SubmissionStatus(str, enum.Enum):
    """Valid status values for an application submission."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class VoteType(str, enum.Enum):
    """Valid vote types for a reviewer's vote on a submission."""

    APPROVE = "approve"
    DENY = "deny"


class ApplicationGuildConfig(db.BASE):
    """Per-guild configuration for the application module."""

    __tablename__ = "ApplicationGuildConfig"

    GuildId = Column(BigInteger, primary_key=True)
    ManagerRoleId = Column(BigInteger, nullable=True)
    ReviewerRoleId = Column(BigInteger, nullable=True)

    @classmethod
    def get(cls, guild_id, session):
        """Returns the config for the given guild."""
        return session.query(cls).filter(cls.GuildId == guild_id).first()

    @classmethod
    def delete(cls, guild_id, session):
        """Deletes the config for the given guild."""
        entry = cls.get(guild_id, session)
        if entry is not None:
            session.delete(entry)


class ApplicationForm(db.BASE):
    """Database entity model for an application form."""

    __tablename__ = "ApplicationForm"
    __table_args__ = (
        Index("ApplicationForm_GuildId", "GuildId"),
        Index("ApplicationForm_Name_GuildId", "Name", "GuildId", unique=True),
        CheckConstraint("RequiredApprovals >= 1", name="ck_form_required_approvals"),
        CheckConstraint("RequiredDenials >= 1", name="ck_form_required_denials"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger, nullable=False)
    Name = Column(Unicode(100), nullable=False)
    ReviewChannelId = Column(BigInteger, nullable=True)
    RequiredApprovals = Column(Integer, nullable=False, default=1)
    RequiredDenials = Column(Integer, nullable=False, default=1)
    ApprovalMessage = Column(UnicodeText, nullable=True)
    DenialMessage = Column(UnicodeText, nullable=True)

    questions = relationship(
        "ApplicationQuestion",
        back_populates="form",
        cascade="all, delete, delete-orphan",
        order_by="ApplicationQuestion.SortOrder",
        lazy="joined",
    )
    submissions = relationship(
        "ApplicationSubmission",
        back_populates="form",
        cascade="all, delete, delete-orphan",
    )

    @classmethod
    def get(cls, name, guild_id, session):
        """Returns a form by name and guild."""
        return session.query(cls).filter(cls.Name == name, cls.GuildId == guild_id).first()

    @classmethod
    def get_by_id(cls, form_id, session):
        """Returns a form by its primary key."""
        return session.query(cls).filter(cls.Id == form_id).first()

    @classmethod
    def get_all_by_guild(cls, guild_id, session):
        """Returns all forms for a guild."""
        return session.query(cls).filter(cls.GuildId == guild_id).order_by(cls.Name).all()

    @classmethod
    def get_ready_by_guild(cls, guild_id, session):
        """Returns forms that have a ReviewChannelId set (ready to accept submissions)."""
        return (
            session.query(cls).filter(cls.GuildId == guild_id, cls.ReviewChannelId.isnot(None)).order_by(cls.Name).all()
        )

    @classmethod
    def delete_by_name(cls, name, guild_id, session):
        """Deletes a form by name and guild."""
        form = cls.get(name, guild_id, session)
        if form is not None:
            session.delete(form)


class ApplicationQuestion(db.BASE):
    """Database entity model for a question within an application form."""

    __tablename__ = "ApplicationQuestion"
    __table_args__ = (
        Index("ApplicationQuestion_FormId", "FormId"),
        Index("ApplicationQuestion_FormId_SortOrder", "FormId", "SortOrder", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    FormId = Column(Integer, ForeignKey("ApplicationForm.Id"), nullable=False)
    QuestionText = Column(UnicodeText, nullable=False)
    SortOrder = Column(Integer, nullable=False)

    form = relationship("ApplicationForm", back_populates="questions")


class ApplicationSubmission(db.BASE):
    """Database entity model for a user's submission to an application form."""

    __tablename__ = "ApplicationSubmission"
    __table_args__ = (
        Index("ApplicationSubmission_GuildId", "GuildId"),
        Index("ApplicationSubmission_FormId", "FormId"),
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
    )

    @classmethod
    def get_by_id(cls, submission_id, session):
        """Returns a submission by its primary key."""
        return session.query(cls).filter(cls.Id == submission_id).first()

    @classmethod
    def get_by_review_message(cls, message_id, session):
        """Returns a submission by its review message ID."""
        return session.query(cls).filter(cls.ReviewMessageId == message_id).first()

    @classmethod
    def get_by_guild(cls, guild_id, session):
        """Returns all submissions for a guild."""
        return session.query(cls).filter(cls.GuildId == guild_id).all()

    @classmethod
    def get_by_user_and_form(cls, user_id: int, form_id: int, session):
        """Returns the most recent submission by a user for a given form, or None."""
        return session.query(cls).filter(cls.UserId == user_id, cls.FormId == form_id).order_by(cls.Id.desc()).first()


class ApplicationAnswer(db.BASE):
    """Database entity model for an answer to a question in a submission."""

    __tablename__ = "ApplicationAnswer"
    __table_args__ = (Index("ApplicationAnswer_SubmissionId", "SubmissionId"),)

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


class ApplicationTemplate(db.BASE):
    """Database entity model for reusable application form templates."""

    __tablename__ = "ApplicationTemplate"
    __table_args__ = (
        Index("ApplicationTemplate_GuildId", "GuildId"),
        CheckConstraint(
            "(IsBuiltIn = 1 AND GuildId IS NULL) OR (IsBuiltIn = 0 AND GuildId IS NOT NULL)",
            name="ck_template_builtin_guild",
        ),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger, nullable=True)
    Name = Column(Unicode(100))
    IsBuiltIn = Column(Boolean, default=False)

    questions = relationship(
        "ApplicationTemplateQuestion",
        back_populates="template",
        cascade="all, delete, delete-orphan",
        order_by="ApplicationTemplateQuestion.SortOrder",
        lazy="joined",
    )

    @classmethod
    def get_available(cls, guild_id, session):
        """Returns built-in templates plus guild-specific templates."""
        return (
            session.query(cls)
            .filter((cls.IsBuiltIn.is_(True)) | (cls.GuildId == guild_id))
            .order_by(cls.IsBuiltIn.desc(), cls.Name)
            .all()
        )

    @classmethod
    def get_guild_templates(cls, guild_id, session):
        """Returns guild-specific (non-built-in) templates only."""
        return session.query(cls).filter(cls.GuildId == guild_id, cls.IsBuiltIn.is_(False)).order_by(cls.Name).all()

    @classmethod
    def get_by_name(cls, name, guild_id, session):
        """Returns a template by name — checks built-in and guild-specific."""
        return (
            session.query(cls).filter(cls.Name == name, (cls.IsBuiltIn.is_(True)) | (cls.GuildId == guild_id)).first()
        )


class ApplicationTemplateQuestion(db.BASE):
    """Database entity model for a question within an application template."""

    __tablename__ = "ApplicationTemplateQuestion"
    __table_args__ = (
        Index("ApplicationTemplateQuestion_TemplateId", "TemplateId"),
        Index("ApplicationTemplateQuestion_TemplateId_SortOrder", "TemplateId", "SortOrder", unique=True),
    )

    Id = Column(Integer, primary_key=True)
    TemplateId = Column(Integer, ForeignKey("ApplicationTemplate.Id"), nullable=False)
    QuestionText = Column(UnicodeText, nullable=False)
    SortOrder = Column(Integer, nullable=False)

    template = relationship("ApplicationTemplate", back_populates="questions")


BUILT_IN_TEMPLATES = {
    "Guild Membership": [
        "What is your in-game name or main character?",
        "How did you hear about our guild/community?",
        "What games or activities are you most interested in?",
        "Do you have any previous guild or community experience?",
        "What timezone are you in, and when are you typically available?",
        "Is there anything else you'd like us to know about you?",
    ],
    "Staff / Moderator": [
        "Why are you interested in becoming a staff member or moderator?",
        "Do you have any previous moderation or leadership experience?",
        "How would you handle a situation where two members are in a heated argument?",
        "How many hours per week can you dedicate to moderation duties?",
        "What timezone are you in, and when are you typically available?",
        "Is there anything else you'd like us to know about your qualifications?",
    ],
    "Event Sign-Up": [
        "What is your in-game name or character?",
        "Which role or class will you be playing?",
        "Do you have any relevant experience with this type of event?",
        "Are there any scheduling constraints we should know about?",
        "Any additional notes or questions for the organizers?",
    ],
}


def seed_built_in_templates(session):
    """Seed built-in templates into DB if not already present."""
    for name, questions in BUILT_IN_TEMPLATES.items():
        existing = (
            session.query(ApplicationTemplate)
            .filter(ApplicationTemplate.Name == name, ApplicationTemplate.IsBuiltIn.is_(True))
            .first()
        )
        if existing:
            continue
        template = ApplicationTemplate(Name=name, GuildId=None, IsBuiltIn=True)
        session.add(template)
        session.flush()
        for i, q_text in enumerate(questions, start=1):
            session.add(ApplicationTemplateQuestion(TemplateId=template.Id, QuestionText=q_text, SortOrder=i))
