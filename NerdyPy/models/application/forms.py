# -*- coding: utf-8 -*-
"""Application form and template models."""

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, ForeignKey, Index, Integer, Unicode, UnicodeText
from sqlalchemy.orm import relationship
from utils import database as db


class ApplicationForm(db.BASE):
    """Database entity model for an application form."""

    __tablename__ = "ApplicationForm"
    __table_args__ = (
        Index("ApplicationForm_GuildId", "GuildId"),
        Index("ApplicationForm_Name_GuildId", "Name", "GuildId", unique=True),
        CheckConstraint('"RequiredApprovals" >= 1', name="ck_form_required_approvals"),
        CheckConstraint('"RequiredDenials" >= 1', name="ck_form_required_denials"),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger, nullable=False)
    Name = Column(Unicode(100), nullable=False)
    ReviewChannelId = Column(BigInteger, nullable=True)
    RequiredApprovals = Column(Integer, nullable=False, default=1)
    RequiredDenials = Column(Integer, nullable=False, default=1)
    ApprovalMessage = Column(UnicodeText, nullable=True)
    DenialMessage = Column(UnicodeText, nullable=True)
    ApplyChannelId = Column(BigInteger, nullable=True)
    ApplyMessageId = Column(BigInteger, nullable=True)
    ApplyDescription = Column(UnicodeText, nullable=True)

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
    def delete_by_name(cls, name, guild_id, session):
        """Deletes a form by name and guild."""
        form = cls.get(name, guild_id, session)
        if form is not None:
            session.delete(form)

    @classmethod
    def get_by_apply_message(cls, message_id, session):
        """Look up a form by its apply button message ID."""
        return session.query(cls).filter(cls.ApplyMessageId == message_id).first()


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


class ApplicationTemplate(db.BASE):
    """Database entity model for reusable application form templates."""

    __tablename__ = "ApplicationTemplate"
    __table_args__ = (
        Index("ApplicationTemplate_GuildId", "GuildId"),
        CheckConstraint(
            '("IsBuiltIn" IS TRUE AND "GuildId" IS NULL) OR ("IsBuiltIn" IS FALSE AND "GuildId" IS NOT NULL)',
            name="ck_template_builtin_guild",
        ),
    )

    Id = Column(Integer, primary_key=True)
    GuildId = Column(BigInteger, nullable=True)
    Name = Column(Unicode(100), nullable=False)
    IsBuiltIn = Column(Boolean, default=False)
    ApprovalMessage = Column(UnicodeText, nullable=True)
    DenialMessage = Column(UnicodeText, nullable=True)

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
    def get_by_id(cls, template_id, session):
        """Returns a template by primary key."""
        return session.query(cls).filter(cls.Id == template_id).first()

    @classmethod
    def get_by_name(cls, name, guild_id, session):
        """Returns a template by name — checks built-in and guild-specific."""
        return (
            session.query(cls)
            .filter(cls.Name == name, (cls.IsBuiltIn.is_(True)) | (cls.GuildId == guild_id))
            .order_by(cls.IsBuiltIn.asc())
            .first()
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


TEMPLATE_KEY_MAP: dict[str, str] = {
    "Guild Membership": "guild_membership",
    "Staff / Moderator": "staff_moderator",
    "Partnership / Collaboration": "partnership_collaboration",
    "Volunteer": "volunteer",
    "Community Access": "community_access",
}

BUILT_IN_TEMPLATES: dict[str, list[str]] = {
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
    "Partnership / Collaboration": [
        "Tell us about your community or project — what do you do?",
        "How many active members or participants do you have?",
        "What kind of collaboration are you looking for?",
        "What value would this partnership bring to both communities?",
        "Who is the primary point of contact, and how can we reach them?",
    ],
    "Volunteer": [
        "What areas or tasks are you most interested in volunteering for?",
        "How many hours per week can you commit?",
        "Do you have any relevant skills or experience?",
        "What timezone are you in, and when are you typically available?",
        "Why do you want to volunteer with us?",
    ],
    "Community Access": [
        "Which channel or area are you requesting access to, and why?",
        "How long have you been a member of this server?",
        "Have you read and agreed to the server rules?",
        "How do you plan to use this access?",
    ],
}
