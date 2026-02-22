# -*- coding: utf-8 -*-
"""Tests for DM conversation flows: create, edit, and submit application forms."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from models.application import ApplicationAnswer, ApplicationForm, ApplicationQuestion, ApplicationSubmission
from modules.conversations.application import (
    CANCEL_EMOJI,
    CONFIRM_EMOJI,
    REORDER_EMOJI,
    REMOVE_EMOJI,
    ApplicationCreateConversation,
    ApplicationEditConversation,
    ApplicationSubmitConversation,
    CreateState,
    EditState,
    SubmitState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_send_return(user_mock):
    """Set up user.send to return a mock message with add_reaction."""
    sent = MagicMock()
    sent.id = 999
    sent.add_reaction = AsyncMock()
    user_mock.send = AsyncMock(return_value=sent)
    return sent


# ---------------------------------------------------------------------------
# TestApplicationCreateConversation
# ---------------------------------------------------------------------------


class TestApplicationCreateConversation:
    """Tests for ApplicationCreateConversation."""

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild):
        _make_send_return(mock_user)
        return ApplicationCreateConversation(mock_bot, mock_user, mock_guild, "Test Form", review_channel_id=123)

    @pytest.mark.asyncio
    async def test_initial_state_sends_dm(self, conv, mock_user):
        """Init state sends an embed to the user via DM."""
        await conv.repost_state()

        mock_user.send.assert_called_once()
        kwargs = mock_user.send.call_args
        embed = kwargs.kwargs.get("embed") or kwargs[1].get("embed")
        assert "Test Form" in embed.title

    @pytest.mark.asyncio
    async def test_collecting_questions_loops(self, conv, mock_user):
        """Sending text messages adds questions and stays in COLLECT."""
        await conv.repost_state()  # INIT
        mock_user.send.reset_mock()
        _make_send_return(mock_user)

        # Simulate user typing a question
        await conv.on_message("What is your name?")

        assert len(conv.questions) == 1
        assert conv.questions[0] == "What is your name?"
        assert conv.currentState == CreateState.COLLECT

        # Another question
        mock_user.send.reset_mock()
        _make_send_return(mock_user)
        await conv.on_message("What is your class?")

        assert len(conv.questions) == 2
        assert conv.questions[1] == "What is your class?"
        assert conv.currentState == CreateState.COLLECT

    @pytest.mark.asyncio
    async def test_cancel_reaction_transitions_to_done(self, conv, mock_user):
        """Reacting ❌ transitions to DONE and closes."""
        await conv.repost_state()  # INIT
        mock_user.send.reset_mock()
        _make_send_return(mock_user)

        # React ❌ — but no questions collected, so it shows error and closes
        await conv.on_react(CANCEL_EMOJI)

        assert conv.isActive is False

    @pytest.mark.asyncio
    async def test_no_questions_shows_error(self, conv, mock_user):
        """Reacting ❌ with zero questions sends error message and closes."""
        await conv.repost_state()  # INIT
        mock_user.send.reset_mock()
        _make_send_return(mock_user)

        await conv.on_react(CANCEL_EMOJI)

        # Should have sent "at least one question" error via embed
        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("at least one question" in (e.description or "") for e in embeds)
        assert conv.isActive is False

    @pytest.mark.asyncio
    async def test_done_creates_form_in_db(self, conv, mock_user, db_session):
        """Collecting questions then finishing creates DB rows."""
        await conv.repost_state()  # INIT

        # Collect two questions
        _make_send_return(mock_user)
        await conv.on_message("Question one?")
        _make_send_return(mock_user)
        await conv.on_message("Question two?")

        # Finish
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        assert conv.isActive is False

        # Verify DB
        form = db_session.query(ApplicationForm).filter(ApplicationForm.Name == "Test Form").first()
        assert form is not None
        assert form.GuildId == 987654321
        assert form.ReviewChannelId == 123
        assert form.RequiredApprovals == 1  # ORM default preserved when not passed
        assert form.RequiredDenials == 1  # ORM default preserved when not passed

        questions = (
            db_session.query(ApplicationQuestion)
            .filter(ApplicationQuestion.FormId == form.Id)
            .order_by(ApplicationQuestion.SortOrder)
            .all()
        )
        assert len(questions) == 2
        assert questions[0].QuestionText == "Question one?"
        assert questions[0].SortOrder == 1
        assert questions[1].QuestionText == "Question two?"
        assert questions[1].SortOrder == 2

    @pytest.mark.asyncio
    async def test_done_saves_review_channel_id(self, mock_bot, mock_user, mock_guild, db_session):
        """Form is created with ReviewChannelId passed to the conversation."""
        _make_send_return(mock_user)
        conv = ApplicationCreateConversation(mock_bot, mock_user, mock_guild, "Chan Form", review_channel_id=42)
        await conv.repost_state()
        _make_send_return(mock_user)
        await conv.on_message("Question?")
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        form = db_session.query(ApplicationForm).filter(ApplicationForm.Name == "Chan Form").first()
        assert form is not None
        assert form.ReviewChannelId == 42

    @pytest.mark.asyncio
    async def test_done_saves_optional_settings(self, mock_bot, mock_user, mock_guild, db_session):
        """Optional settings passed to conversation are written to the form."""
        _make_send_return(mock_user)
        conv = ApplicationCreateConversation(
            mock_bot,
            mock_user,
            mock_guild,
            "Settings Form",
            review_channel_id=55,
            required_approvals=3,
            required_denials=2,
            approval_message="Welcome!",
            denial_message="Sorry.",
        )
        await conv.repost_state()
        _make_send_return(mock_user)
        await conv.on_message("Question?")
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        form = db_session.query(ApplicationForm).filter(ApplicationForm.Name == "Settings Form").first()
        assert form.ReviewChannelId == 55
        assert form.RequiredApprovals == 3
        assert form.RequiredDenials == 2
        assert form.ApprovalMessage == "Welcome!"
        assert form.DenialMessage == "Sorry."

    @pytest.mark.asyncio
    async def test_done_saves_apply_channel_and_description(self, mock_bot, mock_user, mock_guild, db_session):
        """ApplyChannelId and ApplyDescription are persisted when provided."""
        _make_send_return(mock_user)
        conv = ApplicationCreateConversation(
            mock_bot,
            mock_user,
            mock_guild,
            "Apply Form",
            review_channel_id=55,
            apply_channel_id=999,
            apply_description="Click to apply!",
        )
        await conv.repost_state()
        _make_send_return(mock_user)
        await conv.on_message("Question?")
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        form = db_session.query(ApplicationForm).filter(ApplicationForm.Name == "Apply Form").first()
        assert form is not None
        assert form.ApplyChannelId == 999
        assert form.ApplyDescription == "Click to apply!"


# ---------------------------------------------------------------------------
# TestApplicationEditConversation
# ---------------------------------------------------------------------------


class TestApplicationEditConversation:
    """Tests for ApplicationEditConversation."""

    @pytest.fixture
    def form_id(self, db_session, mock_guild):
        """Create a form with two questions in the DB."""
        form = ApplicationForm(GuildId=mock_guild.id, Name="Edit Form")
        db_session.add(form)
        db_session.flush()
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="First?", SortOrder=1))
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="Second?", SortOrder=2))
        db_session.flush()
        return form.Id

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild, form_id):
        _make_send_return(mock_user)
        return ApplicationEditConversation(mock_bot, mock_user, mock_guild, form_id)

    @pytest.mark.asyncio
    async def test_init_shows_current_questions(self, conv, mock_user):
        """INIT state shows numbered question list."""
        await conv.repost_state()

        mock_user.send.assert_called_once()
        kwargs = mock_user.send.call_args
        embed = kwargs.kwargs.get("embed") or kwargs[1].get("embed")
        assert "Edit Form" in embed.title
        assert "First?" in embed.description
        assert "Second?" in embed.description

    @pytest.mark.asyncio
    async def test_add_question(self, conv, mock_user, db_session, form_id):
        """Add flow appends a question and returns to INIT."""
        await conv.repost_state()  # INIT

        # React with 📝 to go to ADD state
        _make_send_return(mock_user)
        await conv.on_react("\U0001f4dd")
        assert conv.currentState == EditState.ADD

        # Type a new question
        _make_send_return(mock_user)
        await conv.on_message("Third?")

        # Should be back at INIT with 3 questions
        assert conv.currentState == EditState.INIT

        questions = (
            db_session.query(ApplicationQuestion)
            .filter(ApplicationQuestion.FormId == form_id)
            .order_by(ApplicationQuestion.SortOrder)
            .all()
        )
        assert len(questions) == 3
        assert questions[2].QuestionText == "Third?"
        assert questions[2].SortOrder == 3

    @pytest.mark.asyncio
    async def test_remove_question(self, conv, mock_user, db_session, form_id):
        """Remove flow deletes a question and reorders remaining."""
        await conv.repost_state()  # INIT

        # React with 🗑️ to go to REMOVE state
        _make_send_return(mock_user)
        await conv.on_react("\U0001f5d1\ufe0f")
        assert conv.currentState == EditState.REMOVE

        # Type the number to remove
        _make_send_return(mock_user)
        await conv.on_message("1")

        # Should be back at INIT
        assert conv.currentState == EditState.INIT

        questions = (
            db_session.query(ApplicationQuestion)
            .filter(ApplicationQuestion.FormId == form_id)
            .order_by(ApplicationQuestion.SortOrder)
            .all()
        )
        assert len(questions) == 1
        assert questions[0].QuestionText == "Second?"
        assert questions[0].SortOrder == 1

    @pytest.mark.asyncio
    async def test_done_closes_conversation(self, conv, mock_user):
        """Reacting ✅ closes the conversation."""
        await conv.repost_state()  # INIT

        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        assert conv.currentState == EditState.DONE
        assert conv.isActive is False

    @pytest.mark.asyncio
    async def test_reorder_questions(self, conv, mock_user, db_session, form_id):
        """Reorder flow swaps question order and returns to INIT."""
        await conv.repost_state()  # INIT

        # React with 🔀 to go to REORDER state
        _make_send_return(mock_user)
        await conv.on_react(REORDER_EMOJI)
        assert conv.currentState == EditState.REORDER

        # Provide new order: swap the two questions
        _make_send_return(mock_user)
        await conv.on_message("2,1")

        # Should be back at INIT
        assert conv.currentState == EditState.INIT

        questions = (
            db_session.query(ApplicationQuestion)
            .filter(ApplicationQuestion.FormId == form_id)
            .order_by(ApplicationQuestion.SortOrder)
            .all()
        )
        assert len(questions) == 2
        assert questions[0].QuestionText == "Second?"
        assert questions[0].SortOrder == 1
        assert questions[1].QuestionText == "First?"
        assert questions[1].SortOrder == 2

    @pytest.mark.asyncio
    async def test_remove_invalid_number(self, conv, mock_user):
        """Providing a non-numeric or out-of-range number to remove is rejected."""
        await conv.repost_state()  # INIT

        # React with 🗑️ to go to REMOVE state
        _make_send_return(mock_user)
        await conv.on_react(REMOVE_EMOJI)
        assert conv.currentState == EditState.REMOVE

        # Try non-numeric input
        _make_send_return(mock_user)
        await conv.on_message("abc")

        # Should stay in REMOVE (validation failed, waiting for valid input)
        assert conv.currentState == EditState.REMOVE

        # Verify error embed was sent
        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("valid number" in (e.description or "").lower() for e in embeds)

        # Try out-of-range number
        mock_user.send.reset_mock()
        _make_send_return(mock_user)
        await conv.on_message("5")

        # Should still be in REMOVE
        assert conv.currentState == EditState.REMOVE

        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("between 1 and" in (e.description or "").lower() for e in embeds)

    @pytest.mark.asyncio
    async def test_reorder_invalid_input(self, conv, mock_user):
        """Providing invalid reorder input (non-numeric or wrong number set) is rejected."""
        await conv.repost_state()  # INIT

        # React with 🔀 to go to REORDER state
        _make_send_return(mock_user)
        await conv.on_react(REORDER_EMOJI)
        assert conv.currentState == EditState.REORDER

        # Non-numeric input — should stay in REORDER
        _make_send_return(mock_user)
        await conv.on_message("abc,def")

        assert conv.currentState == EditState.REORDER

        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("comma-separated numbers" in (e.description or "").lower() for e in embeds)

        # Wrong number set (only 2 questions, but provide 3) — should stay in REORDER
        mock_user.send.reset_mock()
        _make_send_return(mock_user)
        await conv.on_message("1,2,3")

        assert conv.currentState == EditState.REORDER

        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("exactly once" in (e.description or "").lower() for e in embeds)


# ---------------------------------------------------------------------------
# TestApplicationSubmitConversation
# ---------------------------------------------------------------------------


class TestApplicationSubmitConversation:
    """Tests for ApplicationSubmitConversation."""

    @pytest.fixture
    def questions(self):
        """Sample questions list as (id, text) tuples."""
        return [(10, "What is your name?"), (20, "What is your class?"), (30, "Why do you want to join?")]

    @pytest.fixture
    def mock_review_channel(self):
        """Mock channel for review embed posting."""
        channel = MagicMock()
        review_msg = MagicMock()
        review_msg.id = 888777666
        channel.send = AsyncMock(return_value=review_msg)
        return channel

    @pytest.fixture
    def form_id(self, db_session, mock_guild):
        """Create a form in the DB for submissions."""
        form = ApplicationForm(GuildId=mock_guild.id, Name="Submit Form", ReviewChannelId=111222333)
        db_session.add(form)
        db_session.flush()
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="What is your name?", SortOrder=1))
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="What is your class?", SortOrder=2))
        db_session.add(ApplicationQuestion(FormId=form.Id, QuestionText="Why do you want to join?", SortOrder=3))
        db_session.flush()
        # Return the real question IDs for use in the conversation
        questions = (
            db_session.query(ApplicationQuestion)
            .filter(ApplicationQuestion.FormId == form.Id)
            .order_by(ApplicationQuestion.SortOrder)
            .all()
        )
        return form.Id, [(q.Id, q.QuestionText) for q in questions]

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild, form_id, mock_review_channel):
        _make_send_return(mock_user)
        mock_bot.get_channel = MagicMock(return_value=mock_review_channel)
        fid, qs = form_id
        return ApplicationSubmitConversation(mock_bot, mock_user, mock_guild, fid, "Submit Form", qs)

    @pytest.mark.asyncio
    async def test_walks_through_all_questions(self, conv, mock_user):
        """Answering each question advances through all question states."""
        await conv.repost_state()  # INIT -> question_0

        # Answer question 0
        _make_send_return(mock_user)
        await conv.on_message("Alice")
        assert conv.currentState == "question_1"

        # Answer question 1
        _make_send_return(mock_user)
        await conv.on_message("Mage")
        assert conv.currentState == "question_2"

        # Answer question 2
        _make_send_return(mock_user)
        await conv.on_message("Fun guild!")
        assert conv.currentState == SubmitState.CONFIRM

        assert len(conv.answers) == 3

    @pytest.mark.asyncio
    async def test_cancel_midway(self, conv, mock_user):
        """Reacting ❌ on a question cancels the submission."""
        await conv.repost_state()  # INIT -> question_0

        # Answer question 0
        _make_send_return(mock_user)
        await conv.on_message("Alice")

        # Cancel on question 1
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        assert conv.currentState == SubmitState.CANCELLED
        assert conv.isActive is False
        assert conv.submission_id is None

    @pytest.mark.asyncio
    async def test_confirm_and_submit(self, conv, mock_user, mock_review_channel, db_session):
        """Complete all questions, confirm, and verify DB submission + review embed."""
        await conv.repost_state()  # INIT -> question_0

        # Answer all three questions
        for answer in ["Alice", "Mage", "Fun guild!"]:
            _make_send_return(mock_user)
            await conv.on_message(answer)

        # Now at CONFIRM — react ✅ to submit
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        assert conv.currentState == SubmitState.SUBMIT
        assert conv.isActive is False
        assert conv.submission_id is not None

        # Verify DB submission
        submission = (
            db_session.query(ApplicationSubmission).filter(ApplicationSubmission.Id == conv.submission_id).one()
        )
        assert submission.Status == "pending"
        assert submission.UserId == 123456789
        assert submission.ReviewMessageId == 888777666

        answers = db_session.query(ApplicationAnswer).filter(ApplicationAnswer.SubmissionId == submission.Id).all()
        assert len(answers) == 3

        # Verify review embed was posted to the channel
        mock_review_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_last_activity_updated(self, conv, mock_user):
        """last_activity should update on each message."""
        before = conv.last_activity
        await conv.repost_state()  # INIT -> question_0

        _make_send_return(mock_user)
        await conv.on_message("Alice")

        assert conv.last_activity >= before

    @pytest.mark.asyncio
    async def test_submission_id_set_after_submit(self, conv, mock_user):
        """submission_id should be None before submit and set after."""
        assert conv.submission_id is None

        await conv.repost_state()  # INIT -> question_0

        for answer in ["Alice", "Mage", "Fun guild!"]:
            _make_send_return(mock_user)
            await conv.on_message(answer)

        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        assert conv.submission_id is not None

    @pytest.mark.asyncio
    async def test_submit_channel_unreachable(self, mock_bot, mock_user, mock_guild, form_id, db_session):
        """When the review channel is unreachable, no submission is saved and the guild owner is DMed."""
        _make_send_return(mock_user)

        # Make both get_channel and fetch_channel fail — simulates deleted/forbidden channel.
        mock_bot.get_channel = MagicMock(return_value=None)
        mock_bot.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "Unknown Channel"))

        # Track the DM sent to the guild owner.
        mock_owner = MagicMock()
        mock_owner.send = AsyncMock()
        mock_bot.fetch_user = AsyncMock(return_value=mock_owner)
        mock_guild.owner_id = 999000111

        fid, qs = form_id
        conv = ApplicationSubmitConversation(mock_bot, mock_user, mock_guild, fid, "Submit Form", qs)

        await conv.repost_state()  # INIT -> question_0

        for answer in ["Alice", "Mage", "Fun guild!"]:
            _make_send_return(mock_user)
            await conv.on_message(answer)

        # React ✅ to trigger state_submit
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        # No submission should have been saved
        assert conv.submission_id is None
        assert db_session.query(ApplicationSubmission).count() == 0

        # User should have received an error embed
        all_embeds = [c.kwargs.get("embed") for c in mock_user.send.call_args_list if c.kwargs.get("embed")]
        assert any("submission error" in (e.title or "").lower() for e in all_embeds)

        # Guild owner was notified
        mock_owner.send.assert_called_once()


class TestSubmitConversationRoleMentions:
    """Review embed should mention admin + configured roles in message content."""

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild, db_session):
        _make_send_return(mock_user)
        form = ApplicationForm(GuildId=mock_guild.id, Name="F", ReviewChannelId=555)
        db_session.add(form)
        db_session.flush()
        q = ApplicationQuestion(FormId=form.Id, QuestionText="Q1", SortOrder=1)
        db_session.add(q)
        db_session.flush()
        return ApplicationSubmitConversation(
            mock_bot, mock_user, mock_guild,
            form_id=form.Id, form_name="F",
            questions=[(q.Id, "Q1")],
        )

    @pytest.mark.asyncio
    async def test_mentions_admin_roles(self, conv, mock_bot, mock_guild):
        admin_role = MagicMock()
        admin_role.id = 888
        admin_role.permissions = MagicMock()
        admin_role.permissions.administrator = True
        mock_guild.roles = [admin_role]

        channel = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 777
        channel.send = AsyncMock(return_value=sent_msg)
        mock_bot.get_channel = MagicMock(return_value=channel)

        conv.answers = {conv.questions[0][0]: "answer"}
        conv.currentState = SubmitState.SUBMIT
        await conv.repost_state()

        content = channel.send.call_args.kwargs.get("content")
        assert "<@&888>" in (content or "")

    @pytest.mark.asyncio
    async def test_mentions_configured_roles(self, conv, mock_bot, mock_guild, db_session):
        from models.application import ApplicationGuildConfig
        db_session.add(ApplicationGuildConfig(GuildId=mock_guild.id, ManagerRoleId=111, ReviewerRoleId=222))
        db_session.flush()
        mock_guild.roles = []

        channel = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 777
        channel.send = AsyncMock(return_value=sent_msg)
        mock_bot.get_channel = MagicMock(return_value=channel)

        conv.answers = {conv.questions[0][0]: "answer"}
        conv.currentState = SubmitState.SUBMIT
        await conv.repost_state()

        content = channel.send.call_args.kwargs.get("content")
        assert "<@&111>" in (content or "")
        assert "<@&222>" in (content or "")

    @pytest.mark.asyncio
    async def test_no_content_when_no_roles(self, conv, mock_bot, mock_guild):
        mock_guild.roles = []  # no admin roles, no config

        channel = MagicMock()
        sent_msg = MagicMock()
        sent_msg.id = 777
        channel.send = AsyncMock(return_value=sent_msg)
        mock_bot.get_channel = MagicMock(return_value=channel)

        conv.answers = {conv.questions[0][0]: "answer"}
        conv.currentState = SubmitState.SUBMIT
        await conv.repost_state()

        content = channel.send.call_args.kwargs.get("content")
        assert not content
