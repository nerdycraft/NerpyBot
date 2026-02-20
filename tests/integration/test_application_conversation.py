# -*- coding: utf-8 -*-
"""Tests for DM conversation flows: create, edit, and submit application forms."""

from unittest.mock import AsyncMock, MagicMock

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


def _make_mock_message(content: str) -> MagicMock:
    """Create a mock discord.Message with the given content."""
    msg = MagicMock()
    msg.content = content
    return msg


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
        return ApplicationCreateConversation(mock_bot, mock_user, mock_guild, "Test Form")

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
        await conv.on_message(_make_mock_message("What is your name?"))

        assert len(conv.questions) == 1
        assert conv.questions[0] == "What is your name?"
        assert conv.currentState == CreateState.COLLECT

        # Another question
        mock_user.send.reset_mock()
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("What is your class?"))

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
        await conv.on_message(_make_mock_message("Question one?"))
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("Question two?"))

        # Finish
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        assert conv.isActive is False

        # Verify DB
        form = db_session.query(ApplicationForm).filter(ApplicationForm.Name == "Test Form").first()
        assert form is not None
        assert form.GuildId == 987654321

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
        await conv.on_message(_make_mock_message("Third?"))

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
        await conv.on_message(_make_mock_message("1"))

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
        await conv.on_message(_make_mock_message("2,1"))

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
        await conv.on_message(_make_mock_message("abc"))

        # Should stay in REMOVE (validation failed, waiting for valid input)
        assert conv.currentState == EditState.REMOVE

        # Verify error embed was sent
        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("valid number" in (e.description or "").lower() for e in embeds)

        # Try out-of-range number
        mock_user.send.reset_mock()
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("5"))

        # Should still be in REMOVE
        assert conv.currentState == EditState.REMOVE

        calls = mock_user.send.call_args_list
        embeds = [c.kwargs.get("embed") for c in calls if c.kwargs.get("embed") is not None]
        assert any("between 1 and" in (e.description or "").lower() for e in embeds)


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
    def form_id(self, db_session, mock_guild):
        """Create a form in the DB for submissions."""
        form = ApplicationForm(GuildId=mock_guild.id, Name="Submit Form")
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
    def conv(self, mock_bot, mock_user, mock_guild, form_id):
        _make_send_return(mock_user)
        fid, qs = form_id
        return ApplicationSubmitConversation(mock_bot, mock_user, mock_guild, fid, "Submit Form", qs)

    @pytest.mark.asyncio
    async def test_walks_through_all_questions(self, conv, mock_user):
        """Answering each question advances through all question states."""
        await conv.repost_state()  # INIT -> question_0

        # Answer question 0
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("Alice"))
        assert conv.currentState == "question_1"

        # Answer question 1
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("Mage"))
        assert conv.currentState == "question_2"

        # Answer question 2
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("Fun guild!"))
        assert conv.currentState == SubmitState.CONFIRM

        assert len(conv.answers) == 3

    @pytest.mark.asyncio
    async def test_cancel_midway(self, conv, mock_user):
        """Reacting ❌ on a question cancels the submission."""
        await conv.repost_state()  # INIT -> question_0

        # Answer question 0
        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("Alice"))

        # Cancel on question 1
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        assert conv.currentState == SubmitState.CANCELLED
        assert conv.isActive is False
        assert conv.submission_id is None

    @pytest.mark.asyncio
    async def test_confirm_and_submit(self, conv, mock_user, db_session):
        """Complete all questions, confirm, and verify DB submission."""
        await conv.repost_state()  # INIT -> question_0

        # Answer all three questions
        for answer in ["Alice", "Mage", "Fun guild!"]:
            _make_send_return(mock_user)
            await conv.on_message(_make_mock_message(answer))

        # Now at CONFIRM — react ✅ to submit
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        assert conv.currentState == SubmitState.SUBMIT
        assert conv.isActive is False
        assert conv.submission_id is not None

        # Verify DB
        submission = (
            db_session.query(ApplicationSubmission).filter(ApplicationSubmission.Id == conv.submission_id).one()
        )
        assert submission.Status == "pending"
        assert submission.UserId == 123456789

        answers = db_session.query(ApplicationAnswer).filter(ApplicationAnswer.SubmissionId == submission.Id).all()
        assert len(answers) == 3

    @pytest.mark.asyncio
    async def test_last_activity_updated(self, conv, mock_user):
        """last_activity should update on each message."""
        before = conv.last_activity
        await conv.repost_state()  # INIT -> question_0

        _make_send_return(mock_user)
        await conv.on_message(_make_mock_message("Alice"))

        assert conv.last_activity >= before

    @pytest.mark.asyncio
    async def test_submission_id_set_after_submit(self, conv, mock_user):
        """submission_id should be None before submit and set after."""
        assert conv.submission_id is None

        await conv.repost_state()  # INIT -> question_0

        for answer in ["Alice", "Mage", "Fun guild!"]:
            _make_send_return(mock_user)
            await conv.on_message(_make_mock_message(answer))

        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        assert conv.submission_id is not None
