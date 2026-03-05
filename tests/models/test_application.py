# -*- coding: utf-8 -*-
"""Tests for models/application.py - Application form database models"""

from datetime import UTC, datetime


from models.application import (
    BUILT_IN_TEMPLATES,
    TEMPLATE_KEY_MAP,
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    ApplicationVote,
    seed_built_in_templates,
)


# ---------------------------------------------------------------------------
# ApplicationForm
# ---------------------------------------------------------------------------
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
