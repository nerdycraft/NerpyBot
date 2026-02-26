# -*- coding: utf-8 -*-
"""Tests for models/application.py - Application form database models"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from models.application import (
    BUILT_IN_TEMPLATES,
    TEMPLATE_KEY_MAP,
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    ApplicationVote,
    seed_built_in_templates,
)


# ---------------------------------------------------------------------------
# ApplicationGuildConfig
# ---------------------------------------------------------------------------
class TestApplicationGuildConfig:
    """Tests for ApplicationGuildConfig CRUD."""

    def test_create_and_get(self, db_session):
        """Should store and retrieve a guild config."""
        cfg = ApplicationGuildConfig(GuildId=111)
        db_session.add(cfg)
        db_session.commit()

        result = ApplicationGuildConfig.get(111, db_session)
        assert result is not None
        assert result.GuildId == 111

    def test_get_nonexistent_returns_none(self, db_session):
        assert ApplicationGuildConfig.get(999, db_session) is None

    def test_delete(self, db_session):
        cfg = ApplicationGuildConfig(GuildId=111)
        db_session.add(cfg)
        db_session.commit()

        ApplicationGuildConfig.delete(111, db_session)
        db_session.commit()

        assert ApplicationGuildConfig.get(111, db_session) is None

    def test_delete_nonexistent_is_noop(self, db_session):
        """Deleting a non-existent config should not raise."""
        ApplicationGuildConfig.delete(999, db_session)
        db_session.commit()


# ---------------------------------------------------------------------------
# ApplicationForm
# ---------------------------------------------------------------------------
class TestApplicationFormGet:
    """Tests for ApplicationForm.get()."""

    def test_get_by_name_and_guild(self, db_session):
        form = ApplicationForm(GuildId=111, Name="Recruitment")
        db_session.add(form)
        db_session.commit()

        result = ApplicationForm.get("Recruitment", 111, db_session)
        assert result is not None
        assert result.Name == "Recruitment"

    def test_get_nonexistent_returns_none(self, db_session):
        assert ApplicationForm.get("nope", 111, db_session) is None

    def test_get_wrong_guild_returns_none(self, db_session):
        form = ApplicationForm(GuildId=111, Name="Recruitment")
        db_session.add(form)
        db_session.commit()

        assert ApplicationForm.get("Recruitment", 999, db_session) is None


class TestApplicationFormGetById:
    """Tests for ApplicationForm.get_by_id()."""

    def test_get_existing(self, db_session):
        form = ApplicationForm(GuildId=111, Name="Test")
        db_session.add(form)
        db_session.commit()

        result = ApplicationForm.get_by_id(form.Id, db_session)
        assert result is not None
        assert result.Name == "Test"

    def test_get_nonexistent_returns_none(self, db_session):
        assert ApplicationForm.get_by_id(99999, db_session) is None


class TestApplicationFormGetAllByGuild:
    """Tests for ApplicationForm.get_all_by_guild()."""

    def test_returns_all_for_guild(self, db_session):
        for name in ["Form A", "Form B", "Form C"]:
            db_session.add(ApplicationForm(GuildId=111, Name=name))
        db_session.commit()

        results = ApplicationForm.get_all_by_guild(111, db_session)
        assert len(results) == 3

    def test_excludes_other_guilds(self, db_session):
        db_session.add(ApplicationForm(GuildId=111, Name="G1"))
        db_session.add(ApplicationForm(GuildId=222, Name="G2"))
        db_session.commit()

        results = ApplicationForm.get_all_by_guild(111, db_session)
        assert len(results) == 1
        assert results[0].Name == "G1"


class TestApplicationFormDeleteByName:
    """Tests for ApplicationForm.delete_by_name()."""

    def test_delete_existing(self, db_session):
        db_session.add(ApplicationForm(GuildId=111, Name="ToDelete"))
        db_session.commit()

        ApplicationForm.delete_by_name("ToDelete", 111, db_session)
        db_session.commit()

        assert ApplicationForm.get("ToDelete", 111, db_session) is None

    def test_delete_nonexistent_is_noop(self, db_session):
        ApplicationForm.delete_by_name("nope", 111, db_session)
        db_session.commit()


class TestApplicationFormUniqueConstraint:
    """Tests for the unique constraint on (Name, GuildId)."""

    def test_unique_name_per_guild(self, db_session):
        """Should not allow duplicate form names in the same guild."""
        form1 = ApplicationForm(GuildId=123, Name="test-form", RequiredApprovals=1, RequiredDenials=1)
        db_session.add(form1)
        db_session.commit()

        form2 = ApplicationForm(GuildId=123, Name="test-form", RequiredApprovals=1, RequiredDenials=1)
        db_session.add(form2)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestApplicationFormApplyColumns:
    """Tests for ApplyChannelId, ApplyMessageId, ApplyDescription columns."""

    def test_apply_columns_exist(self, db_session):
        form = ApplicationForm(GuildId=123, Name="ColTest")
        form.ApplyChannelId = 999888777
        form.ApplyMessageId = 111222333
        form.ApplyDescription = "Click to apply!"
        db_session.add(form)
        db_session.flush()

        fetched = db_session.query(ApplicationForm).filter(ApplicationForm.Id == form.Id).first()
        assert fetched.ApplyChannelId == 999888777
        assert fetched.ApplyMessageId == 111222333
        assert fetched.ApplyDescription == "Click to apply!"

    def test_apply_columns_default_to_none(self, db_session):
        form = ApplicationForm(GuildId=123, Name="DefaultTest")
        db_session.add(form)
        db_session.flush()

        fetched = db_session.query(ApplicationForm).filter(ApplicationForm.Id == form.Id).first()
        assert fetched.ApplyChannelId is None
        assert fetched.ApplyMessageId is None
        assert fetched.ApplyDescription is None

    def test_get_by_apply_message(self, db_session):
        form = ApplicationForm(GuildId=123, Name="MsgLookup", ApplyMessageId=555666777)
        db_session.add(form)
        db_session.flush()

        result = ApplicationForm.get_by_apply_message(555666777, db_session)
        assert result is not None
        assert result.Name == "MsgLookup"

    def test_get_by_apply_message_not_found(self, db_session):
        result = ApplicationForm.get_by_apply_message(999999, db_session)
        assert result is None


class TestApplicationFormDefaults:
    """Tests for default column values."""

    def test_default_approvals_and_denials(self, db_session):
        form = ApplicationForm(GuildId=111, Name="Defaults")
        db_session.add(form)
        db_session.commit()

        result = ApplicationForm.get("Defaults", 111, db_session)
        assert result.RequiredApprovals == 1
        assert result.RequiredDenials == 1

    def test_nullable_messages(self, db_session):
        form = ApplicationForm(GuildId=111, Name="NoMsg")
        db_session.add(form)
        db_session.commit()

        result = ApplicationForm.get("NoMsg", 111, db_session)
        assert result.ApprovalMessage is None
        assert result.DenialMessage is None


# ---------------------------------------------------------------------------
# ApplicationQuestion
# ---------------------------------------------------------------------------
class TestApplicationQuestion:
    """Tests for ApplicationQuestion."""

    def test_questions_linked_to_form(self, db_session):
        form = ApplicationForm(GuildId=111, Name="WithQ")
        db_session.add(form)
        db_session.commit()

        q1 = ApplicationQuestion(FormId=form.Id, QuestionText="Q1?", SortOrder=1)
        q2 = ApplicationQuestion(FormId=form.Id, QuestionText="Q2?", SortOrder=2)
        db_session.add_all([q1, q2])
        db_session.commit()

        result = ApplicationForm.get("WithQ", 111, db_session)
        assert len(result.questions) == 2
        assert result.questions[0].QuestionText == "Q1?"
        assert result.questions[1].QuestionText == "Q2?"

    def test_questions_ordered_by_sort_order(self, db_session):
        form = ApplicationForm(GuildId=111, Name="Ordered")
        db_session.add(form)
        db_session.commit()

        # Insert out of order
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="Third", SortOrder=3))
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="First", SortOrder=1))
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="Second", SortOrder=2))
        db_session.commit()

        # Reload to get joined load
        db_session.expire_all()
        result = ApplicationForm.get_by_id(form.Id, db_session)
        texts = [q.QuestionText for q in result.questions]
        assert texts == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# Cascade deletes
# ---------------------------------------------------------------------------
class TestCascadeDeletes:
    """Tests for cascade delete behaviour."""

    def test_deleting_form_cascades_to_questions(self, db_session):
        form = ApplicationForm(GuildId=111, Name="CascadeQ")
        db_session.add(form)
        db_session.commit()

        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="Q?", SortOrder=1))
        db_session.commit()
        q_id = form.questions[0].Id

        ApplicationForm.delete_by_name("CascadeQ", 111, db_session)
        db_session.commit()

        assert db_session.query(ApplicationQuestion).filter(ApplicationQuestion.Id == q_id).first() is None

    def test_deleting_form_cascades_to_submissions(self, db_session):
        form = ApplicationForm(GuildId=111, Name="CascadeS")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()
        sub_id = sub.Id

        ApplicationForm.delete_by_name("CascadeS", 111, db_session)
        db_session.commit()

        assert db_session.query(ApplicationSubmission).filter(ApplicationSubmission.Id == sub_id).first() is None

    def test_deleting_submission_cascades_to_answers(self, db_session):
        form = ApplicationForm(GuildId=111, Name="CascadeA")
        db_session.add(form)
        db_session.commit()

        q = ApplicationQuestion(FormId=form.Id, QuestionText="Q?", SortOrder=1)
        db_session.add(q)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        ans = ApplicationAnswer(SubmissionId=sub.Id, QuestionId=q.Id, AnswerText="A!")
        db_session.add(ans)
        db_session.commit()
        ans_id = ans.Id

        db_session.delete(sub)
        db_session.commit()

        assert db_session.query(ApplicationAnswer).filter(ApplicationAnswer.Id == ans_id).first() is None

    def test_deleting_submission_cascades_to_votes(self, db_session):
        form = ApplicationForm(GuildId=111, Name="CascadeV")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        vote = ApplicationVote(SubmissionId=sub.Id, UserId=99, Vote="approve")
        db_session.add(vote)
        db_session.commit()
        vote_id = vote.Id

        db_session.delete(sub)
        db_session.commit()

        assert db_session.query(ApplicationVote).filter(ApplicationVote.Id == vote_id).first() is None

    def test_deleting_form_cascades_through_submissions_to_answers_and_votes(self, db_session):
        """Full cascade: form -> submission -> answers + votes."""
        form = ApplicationForm(GuildId=111, Name="FullCascade")
        db_session.add(form)
        db_session.commit()

        q = ApplicationQuestion(FormId=form.Id, QuestionText="Q?", SortOrder=1)
        db_session.add(q)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        ans = ApplicationAnswer(SubmissionId=sub.Id, QuestionId=q.Id, AnswerText="A!")
        vote = ApplicationVote(SubmissionId=sub.Id, UserId=99, Vote="approve")
        db_session.add_all([ans, vote])
        db_session.commit()

        ans_id, vote_id, q_id = ans.Id, vote.Id, q.Id

        ApplicationForm.delete_by_name("FullCascade", 111, db_session)
        db_session.commit()

        assert db_session.query(ApplicationQuestion).filter(ApplicationQuestion.Id == q_id).first() is None
        assert db_session.query(ApplicationAnswer).filter(ApplicationAnswer.Id == ans_id).first() is None
        assert db_session.query(ApplicationVote).filter(ApplicationVote.Id == vote_id).first() is None


# ---------------------------------------------------------------------------
# ApplicationSubmission
# ---------------------------------------------------------------------------
class TestApplicationSubmissionGetById:
    """Tests for ApplicationSubmission.get_by_id()."""

    def test_get_existing(self, db_session):
        form = ApplicationForm(GuildId=111, Name="SubForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        result = ApplicationSubmission.get_by_id(sub.Id, db_session)
        assert result is not None
        assert result.UserName == "User"

    def test_get_nonexistent_returns_none(self, db_session):
        assert ApplicationSubmission.get_by_id(99999, db_session) is None


class TestApplicationSubmissionGetByReviewMessage:
    """Tests for ApplicationSubmission.get_by_review_message()."""

    def test_get_by_message_id(self, db_session):
        form = ApplicationForm(GuildId=111, Name="MsgForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
            ReviewMessageId=77777,
        )
        db_session.add(sub)
        db_session.commit()

        result = ApplicationSubmission.get_by_review_message(77777, db_session)
        assert result is not None
        assert result.Id == sub.Id

    def test_nonexistent_message_returns_none(self, db_session):
        assert ApplicationSubmission.get_by_review_message(99999, db_session) is None


class TestApplicationSubmissionGetByGuild:
    """Tests for ApplicationSubmission.get_by_guild()."""

    def test_returns_all_for_guild(self, db_session):
        form = ApplicationForm(GuildId=111, Name="GuildForm")
        db_session.add(form)
        db_session.commit()

        for uid in [1, 2, 3]:
            db_session.add(
                ApplicationSubmission(
                    FormId=form.Id,
                    GuildId=111,
                    UserId=uid,
                    UserName=f"User{uid}",
                    Status="pending",
                    SubmittedAt=datetime.now(UTC),
                )
            )
        db_session.commit()

        results = ApplicationSubmission.get_by_guild(111, db_session)
        assert len(results) == 3

    def test_excludes_other_guilds(self, db_session):
        f1 = ApplicationForm(GuildId=111, Name="F1")
        f2 = ApplicationForm(GuildId=222, Name="F2")
        db_session.add_all([f1, f2])
        db_session.commit()

        db_session.add(
            ApplicationSubmission(
                FormId=f1.Id,
                GuildId=111,
                UserId=1,
                UserName="U1",
                Status="pending",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.add(
            ApplicationSubmission(
                FormId=f2.Id,
                GuildId=222,
                UserId=2,
                UserName="U2",
                Status="pending",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.commit()

        results = ApplicationSubmission.get_by_guild(111, db_session)
        assert len(results) == 1


class TestApplicationSubmissionDefaults:
    """Tests for default column values."""

    def test_default_status_is_pending(self, db_session):
        form = ApplicationForm(GuildId=111, Name="DefForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        result = ApplicationSubmission.get_by_id(sub.Id, db_session)
        assert result.Status == "pending"


# ---------------------------------------------------------------------------
# ApplicationAnswer
# ---------------------------------------------------------------------------
class TestApplicationAnswer:
    """Tests for ApplicationAnswer."""

    def test_answers_linked_to_submission(self, db_session):
        form = ApplicationForm(GuildId=111, Name="AnsForm")
        db_session.add(form)
        db_session.commit()

        q = ApplicationQuestion(FormId=form.Id, QuestionText="Q?", SortOrder=1)
        db_session.add(q)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        ans = ApplicationAnswer(SubmissionId=sub.Id, QuestionId=q.Id, AnswerText="My answer")
        db_session.add(ans)
        db_session.commit()

        result = ApplicationSubmission.get_by_id(sub.Id, db_session)
        assert len(result.answers) == 1
        assert result.answers[0].AnswerText == "My answer"


# ---------------------------------------------------------------------------
# ApplicationVote
# ---------------------------------------------------------------------------
class TestApplicationVoteGetBySubmission:
    """Tests for ApplicationVote.get_by_submission()."""

    def test_returns_all_votes(self, db_session):
        form = ApplicationForm(GuildId=111, Name="VoteForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=1, Vote="approve"))
        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=2, Vote="deny"))
        db_session.commit()

        votes = ApplicationVote.get_by_submission(sub.Id, db_session)
        assert len(votes) == 2


class TestApplicationVoteGetUserVote:
    """Tests for ApplicationVote.get_user_vote()."""

    def test_returns_existing_vote(self, db_session):
        form = ApplicationForm(GuildId=111, Name="UVForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=99, Vote="approve"))
        db_session.commit()

        result = ApplicationVote.get_user_vote(sub.Id, 99, db_session)
        assert result is not None
        assert result.Vote == "approve"

    def test_returns_none_when_no_vote(self, db_session):
        form = ApplicationForm(GuildId=111, Name="NoVForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        assert ApplicationVote.get_user_vote(sub.Id, 99, db_session) is None


class TestApplicationVoteCountByType:
    """Tests for ApplicationVote.count_by_type()."""

    def test_counts_correctly(self, db_session):
        form = ApplicationForm(GuildId=111, Name="CntForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=1, Vote="approve"))
        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=2, Vote="approve"))
        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=3, Vote="deny"))
        db_session.commit()

        assert ApplicationVote.count_by_type(sub.Id, "approve", db_session) == 2
        assert ApplicationVote.count_by_type(sub.Id, "deny", db_session) == 1
        assert ApplicationVote.count_by_type(sub.Id, "other", db_session) == 0


class TestApplicationVoteUniqueConstraint:
    """Tests for the unique constraint on (SubmissionId, UserId)."""

    def test_duplicate_vote_raises(self, db_session):
        form = ApplicationForm(GuildId=111, Name="UniqForm")
        db_session.add(form)
        db_session.commit()

        sub = ApplicationSubmission(
            FormId=form.Id,
            GuildId=111,
            UserId=42,
            UserName="User",
            Status="pending",
            SubmittedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()

        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=99, Vote="approve"))
        db_session.commit()

        db_session.add(ApplicationVote(SubmissionId=sub.Id, UserId=99, Vote="deny"))
        with pytest.raises(IntegrityError):
            db_session.commit()


# ---------------------------------------------------------------------------
# ApplicationTemplate
# ---------------------------------------------------------------------------
class TestApplicationTemplateGetAvailable:
    """Tests for ApplicationTemplate.get_available()."""

    def test_returns_builtin_and_guild_specific(self, db_session):
        builtin = ApplicationTemplate(Name="BuiltIn", IsBuiltIn=True)
        guild_tpl = ApplicationTemplate(GuildId=111, Name="Custom", IsBuiltIn=False)
        other_guild = ApplicationTemplate(GuildId=222, Name="Other", IsBuiltIn=False)
        db_session.add_all([builtin, guild_tpl, other_guild])
        db_session.commit()

        results = ApplicationTemplate.get_available(111, db_session)
        names = {t.Name for t in results}
        assert "BuiltIn" in names
        assert "Custom" in names
        assert "Other" not in names

    def test_returns_only_builtin_when_no_guild_templates(self, db_session):
        builtin = ApplicationTemplate(Name="BuiltIn", IsBuiltIn=True)
        db_session.add(builtin)
        db_session.commit()

        results = ApplicationTemplate.get_available(111, db_session)
        assert len(results) == 1
        assert results[0].Name == "BuiltIn"


class TestApplicationTemplateGetGuildTemplates:
    """Tests for ApplicationTemplate.get_guild_templates()."""

    def test_excludes_builtin(self, db_session):
        builtin = ApplicationTemplate(Name="BuiltIn", IsBuiltIn=True)
        guild_tpl = ApplicationTemplate(GuildId=111, Name="Custom", IsBuiltIn=False)
        db_session.add_all([builtin, guild_tpl])
        db_session.commit()

        results = ApplicationTemplate.get_guild_templates(111, db_session)
        assert len(results) == 1
        assert results[0].Name == "Custom"

    def test_excludes_other_guilds(self, db_session):
        db_session.add(ApplicationTemplate(GuildId=111, Name="Mine", IsBuiltIn=False))
        db_session.add(ApplicationTemplate(GuildId=222, Name="Theirs", IsBuiltIn=False))
        db_session.commit()

        results = ApplicationTemplate.get_guild_templates(111, db_session)
        assert len(results) == 1
        assert results[0].Name == "Mine"


class TestApplicationTemplateGetByName:
    """Tests for ApplicationTemplate.get_by_name()."""

    def test_finds_builtin_by_name(self, db_session):
        builtin = ApplicationTemplate(Name="BuiltIn", IsBuiltIn=True)
        db_session.add(builtin)
        db_session.commit()

        result = ApplicationTemplate.get_by_name("BuiltIn", 111, db_session)
        assert result is not None
        assert result.IsBuiltIn is True

    def test_finds_guild_specific_by_name(self, db_session):
        tpl = ApplicationTemplate(GuildId=111, Name="Custom", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        result = ApplicationTemplate.get_by_name("Custom", 111, db_session)
        assert result is not None
        assert result.GuildId == 111

    def test_does_not_find_other_guild_template(self, db_session):
        tpl = ApplicationTemplate(GuildId=222, Name="Other", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        assert ApplicationTemplate.get_by_name("Other", 111, db_session) is None

    def test_returns_none_for_nonexistent(self, db_session):
        assert ApplicationTemplate.get_by_name("Nope", 111, db_session) is None


class TestApplicationTemplateQuestions:
    """Tests for ApplicationTemplateQuestion relationship."""

    def test_message_columns_exist(self, db_session):
        """ApplicationTemplate should have ApprovalMessage and DenialMessage columns."""
        tpl = ApplicationTemplate(
            GuildId=111, Name="MsgTest", IsBuiltIn=False, ApprovalMessage="App!", DenialMessage="Deny!"
        )
        db_session.add(tpl)
        db_session.commit()

        fetched = db_session.query(ApplicationTemplate).filter(ApplicationTemplate.Id == tpl.Id).first()
        assert fetched.ApprovalMessage == "App!"
        assert fetched.DenialMessage == "Deny!"

    def test_message_columns_nullable(self, db_session):
        tpl = ApplicationTemplate(GuildId=111, Name="NoMsg", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        fetched = db_session.query(ApplicationTemplate).filter(ApplicationTemplate.Id == tpl.Id).first()
        assert fetched.ApprovalMessage is None
        assert fetched.DenialMessage is None

    def test_questions_ordered_by_sort_order(self, db_session):
        tpl = ApplicationTemplate(GuildId=111, Name="WithQ", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        db_session.add(ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText="Third", SortOrder=3))
        db_session.add(ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText="First", SortOrder=1))
        db_session.add(ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText="Second", SortOrder=2))
        db_session.commit()

        db_session.expire_all()
        result = ApplicationTemplate.get_by_name("WithQ", 111, db_session)
        texts = [q.QuestionText for q in result.questions]
        assert texts == ["First", "Second", "Third"]

    def test_cascade_delete_to_questions(self, db_session):
        tpl = ApplicationTemplate(GuildId=111, Name="CascadeTpl", IsBuiltIn=False)
        db_session.add(tpl)
        db_session.commit()

        db_session.add(ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText="Q?", SortOrder=1))
        db_session.commit()
        q_id = tpl.questions[0].Id

        db_session.delete(tpl)
        db_session.commit()

        assert (
            db_session.query(ApplicationTemplateQuestion).filter(ApplicationTemplateQuestion.Id == q_id).first()
        ) is None


# ---------------------------------------------------------------------------
# Guild isolation
# ---------------------------------------------------------------------------
class TestGuildIsolation:
    """Tests that guild-scoped queries do not leak data across guilds."""

    def test_forms_are_guild_isolated(self, db_session):
        db_session.add(ApplicationForm(GuildId=111, Name="SharedName"))
        db_session.add(ApplicationForm(GuildId=222, Name="SharedName"))
        db_session.commit()

        r1 = ApplicationForm.get("SharedName", 111, db_session)
        r2 = ApplicationForm.get("SharedName", 222, db_session)
        assert r1.Id != r2.Id

        assert len(ApplicationForm.get_all_by_guild(111, db_session)) == 1
        assert len(ApplicationForm.get_all_by_guild(222, db_session)) == 1

    def test_submissions_are_guild_isolated(self, db_session):
        f1 = ApplicationForm(GuildId=111, Name="F1")
        f2 = ApplicationForm(GuildId=222, Name="F2")
        db_session.add_all([f1, f2])
        db_session.commit()

        db_session.add(
            ApplicationSubmission(
                FormId=f1.Id,
                GuildId=111,
                UserId=1,
                UserName="U1",
                Status="pending",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.add(
            ApplicationSubmission(
                FormId=f2.Id,
                GuildId=222,
                UserId=2,
                UserName="U2",
                Status="pending",
                SubmittedAt=datetime.now(UTC),
            )
        )
        db_session.commit()

        assert len(ApplicationSubmission.get_by_guild(111, db_session)) == 1
        assert len(ApplicationSubmission.get_by_guild(222, db_session)) == 1

    def test_guild_config_is_guild_isolated(self, db_session):
        db_session.add(ApplicationGuildConfig(GuildId=111))
        db_session.add(ApplicationGuildConfig(GuildId=222))
        db_session.commit()

        assert ApplicationGuildConfig.get(111, db_session).GuildId == 111
        assert ApplicationGuildConfig.get(222, db_session).GuildId == 222


# ---------------------------------------------------------------------------
# BUILT_IN_TEMPLATES constant
# ---------------------------------------------------------------------------
class TestTemplateKeyMapConsistency:
    """Tests that TEMPLATE_KEY_MAP stays in sync with BUILT_IN_TEMPLATES."""

    def test_every_builtin_has_key_map_entry(self):
        for name in BUILT_IN_TEMPLATES:
            assert name in TEMPLATE_KEY_MAP, f"BUILT_IN_TEMPLATES key '{name}' missing from TEMPLATE_KEY_MAP"

    def test_every_key_map_entry_has_builtin(self):
        for name in TEMPLATE_KEY_MAP:
            assert name in BUILT_IN_TEMPLATES, f"TEMPLATE_KEY_MAP key '{name}' missing from BUILT_IN_TEMPLATES"

    def test_key_map_values_are_unique(self):
        values = list(TEMPLATE_KEY_MAP.values())
        assert len(values) == len(set(values)), "TEMPLATE_KEY_MAP has duplicate YAML keys"


class TestBuiltInTemplatesConstant:
    """Tests for the BUILT_IN_TEMPLATES dict."""

    def test_has_five_templates(self):
        assert len(BUILT_IN_TEMPLATES) == 5

    def test_guild_membership_has_six_questions(self):
        assert len(BUILT_IN_TEMPLATES["Guild Membership"]) == 6

    def test_staff_moderator_has_six_questions(self):
        assert len(BUILT_IN_TEMPLATES["Staff / Moderator"]) == 6

    def test_community_access_has_four_questions(self):
        assert len(BUILT_IN_TEMPLATES["Community Access"]) == 4

    def test_all_questions_are_strings(self):
        for name, questions in BUILT_IN_TEMPLATES.items():
            for q in questions:
                assert isinstance(q, str), f"Question in '{name}' is not a string: {q!r}"


# ---------------------------------------------------------------------------
# seed_built_in_templates
# ---------------------------------------------------------------------------
class TestBuiltInTemplateSeeding:
    """Tests for the seed_built_in_templates() function."""

    def test_seed_creates_templates(self, db_session):
        """Should create all 5 built-in templates."""
        seed_built_in_templates(db_session)
        db_session.commit()
        templates = ApplicationTemplate.get_available(123, db_session)
        assert len(templates) == 5

    def test_seed_idempotent(self, db_session):
        """Calling seed twice should not create duplicates."""
        seed_built_in_templates(db_session)
        db_session.commit()
        seed_built_in_templates(db_session)
        db_session.commit()
        templates = db_session.query(ApplicationTemplate).filter(ApplicationTemplate.IsBuiltIn.is_(True)).all()
        assert len(templates) == 5

    def test_seed_creates_questions(self, db_session):
        """Each seeded template should have the correct questions."""
        seed_built_in_templates(db_session)
        db_session.commit()
        tpl = ApplicationTemplate.get_by_name("Guild Membership", 123, db_session)
        assert tpl is not None
        assert len(tpl.questions) == 6

    def test_seed_preserves_question_order(self, db_session):
        """Questions should have correct SortOrder."""
        seed_built_in_templates(db_session)
        db_session.commit()
        tpl = ApplicationTemplate.get_by_name("Community Access", 123, db_session)
        orders = [q.SortOrder for q in tpl.questions]
        assert orders == [1, 2, 3, 4]
