# -*- coding: utf-8 -*-
"""Tests for DM conversation flows: create, edit, and submit application forms."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from models.application import ApplicationAnswer, ApplicationForm, ApplicationQuestion, ApplicationSubmission
from utils.strings import load_strings
from modules.conversations.application import (
    BACK_EMOJI,
    CANCEL_EMOJI,
    CONFIRM_EMOJI,
    EDIT_EMOJI,
    LEAVE_EMOJI,
    REORDER_EMOJI,
    REMOVE_EMOJI,
    RESET_EMOJI,
    ApplicationCreateConversation,
    ApplicationEditConversation,
    ApplicationSubmitConversation,
    ApplicationTemplateCreateConversation,
    CreateState,
    EditState,
    SubmitState,
    TemplateCreateState,
)


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


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
    async def test_cancel_reaction_transitions_to_cancel_state(self, conv, mock_user):
        """Reacting ❌ transitions to CANCEL and closes."""
        await conv.repost_state()  # INIT
        mock_user.send.reset_mock()
        _make_send_return(mock_user)

        # React ❌ — transitions to CANCEL and closes
        await conv.on_react(CANCEL_EMOJI)

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

        # Go to review
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)
        assert conv.currentState == CreateState.REVIEW

        # Finish (save)
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

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
        await conv.on_react(CONFIRM_EMOJI)  # review
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # save

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
        await conv.on_react(CONFIRM_EMOJI)  # review
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # save

        form = db_session.query(ApplicationForm).filter(ApplicationForm.Name == "Settings Form").first()
        assert form.ReviewChannelId == 55
        assert form.RequiredApprovals == 3
        assert form.RequiredDenials == 2
        assert form.ApprovalMessage == "Welcome!"
        assert form.DenialMessage == "Sorry."

    @pytest.mark.asyncio
    async def test_done_saves_apply_channel_and_description(self, mock_bot, mock_user, mock_guild, db_session):
        """ApplyChannelId and ApplyDescription are persisted when provided."""
        channel_mock = MagicMock()
        channel_mock.send = AsyncMock(return_value=MagicMock(id=5000))
        mock_bot.get_channel = MagicMock(return_value=channel_mock)
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
        await conv.on_react(CONFIRM_EMOJI)  # review
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # save

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

        # Leave on question 1
        _make_send_return(mock_user)
        await conv.on_react(LEAVE_EMOJI)

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


class TestSubmitConversationNavigation:
    """Back and Reset navigation in ApplicationSubmitConversation."""

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild, db_session):
        _make_send_return(mock_user)
        form = ApplicationForm(GuildId=mock_guild.id, Name="Nav", ReviewChannelId=555)
        db_session.add(form)
        db_session.flush()
        q1 = ApplicationQuestion(FormId=form.Id, QuestionText="Q1", SortOrder=1)
        q2 = ApplicationQuestion(FormId=form.Id, QuestionText="Q2", SortOrder=2)
        db_session.add_all([q1, q2])
        db_session.flush()
        return ApplicationSubmitConversation(
            mock_bot,
            mock_user,
            mock_guild,
            form_id=form.Id,
            form_name="Nav",
            questions=[(q1.Id, "Q1"), (q2.Id, "Q2")],
        )

    @pytest.mark.asyncio
    async def test_back_on_question_2_goes_to_question_1(self, conv):
        await conv.repost_state()  # INIT → question_0
        await conv.on_message("A1")  # → question_1
        await conv.on_react(BACK_EMOJI)
        assert conv.currentState == "question_0"

    @pytest.mark.asyncio
    async def test_back_not_available_on_first_question(self, conv):
        """question_0 should NOT add a ⬅️ reaction."""
        await conv.repost_state()  # INIT → question_0
        sent = conv.user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert BACK_EMOJI not in reaction_calls

    @pytest.mark.asyncio
    async def test_back_preserves_existing_answer_in_embed(self, conv):
        """Going back to a question shows the previously entered answer."""
        await conv.repost_state()
        await conv.on_message("My first answer")  # → question_1
        await conv.on_react(BACK_EMOJI)  # → question_0
        sent_calls = conv.user.send.call_args_list
        last_embed = sent_calls[-1].kwargs.get("embed") or sent_calls[-1][1]["embed"]
        assert "My first answer" in last_embed.description

    @pytest.mark.asyncio
    async def test_reset_clears_answers_and_goes_to_question_1(self, conv):
        await conv.repost_state()
        await conv.on_message("A1")  # question_1
        conv.answers[conv.questions[0][0]] = "A1"  # ensure stored
        await conv.on_react(RESET_EMOJI)
        assert conv.currentState == "question_0"
        assert conv.answers == {}

    @pytest.mark.asyncio
    async def test_reset_not_available_on_first_question(self, conv):
        """question_0 should NOT show 🔄 reset — there's nothing to reset."""
        await conv.repost_state()  # INIT → question_0
        sent = conv.user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert RESET_EMOJI not in reaction_calls

    @pytest.mark.asyncio
    async def test_reset_available_on_second_question(self, conv):
        """question_1 should show 🔄 reset."""
        await conv.repost_state()
        await conv.on_message("A1")  # → question_1
        sent = conv.user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert RESET_EMOJI in reaction_calls

    @pytest.mark.asyncio
    async def test_leave_instruction_in_footer_not_description(self, conv):
        """Leave hint should appear in the embed footer, not the description body."""
        await conv.repost_state()  # INIT → question_0
        sent_calls = conv.user.send.call_args_list
        last_embed = sent_calls[-1].kwargs.get("embed") or sent_calls[-1][1]["embed"]
        # Leave emoji should NOT be in the description
        assert LEAVE_EMOJI not in (last_embed.description or "")
        # But it should appear in the footer text
        assert LEAVE_EMOJI in (last_embed.footer.text if last_embed.footer else "")


class TestSubmitConversationEditBeforeSubmit:
    """Users can edit an answer from the confirm screen before submitting."""

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild, db_session):
        _make_send_return(mock_user)
        form = ApplicationForm(GuildId=mock_guild.id, Name="Edit", ReviewChannelId=555)
        db_session.add(form)
        db_session.flush()
        q1 = ApplicationQuestion(FormId=form.Id, QuestionText="Q1", SortOrder=1)
        q2 = ApplicationQuestion(FormId=form.Id, QuestionText="Q2", SortOrder=2)
        db_session.add_all([q1, q2])
        db_session.flush()
        c = ApplicationSubmitConversation(
            mock_bot,
            mock_user,
            mock_guild,
            form_id=form.Id,
            form_name="Edit",
            questions=[(q1.Id, "Q1"), (q2.Id, "Q2")],
        )
        c.answers = {q1.Id: "Old A1", q2.Id: "Old A2"}
        return c

    @pytest.mark.asyncio
    async def test_confirm_includes_edit_reaction(self, conv):
        conv.currentState = SubmitState.CONFIRM
        await conv.repost_state()
        sent = conv.user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert EDIT_EMOJI in reaction_calls

    @pytest.mark.asyncio
    async def test_edit_reaction_transitions_to_edit_select(self, conv):
        conv.currentState = SubmitState.CONFIRM
        await conv.repost_state()
        await conv.on_react(EDIT_EMOJI)
        assert conv.currentState == SubmitState.EDIT_SELECT

    @pytest.mark.asyncio
    async def test_edit_select_valid_number_jumps_to_question(self, conv):
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("1")
        assert conv.currentState == "question_0"

    @pytest.mark.asyncio
    async def test_edit_select_invalid_number_stays(self, conv):
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("99")  # out of range
        assert conv.currentState == SubmitState.EDIT_SELECT

    @pytest.mark.asyncio
    async def test_edit_select_non_numeric_stays(self, conv):
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("abc")
        assert conv.currentState == SubmitState.EDIT_SELECT

    @pytest.mark.asyncio
    async def test_edit_returns_to_confirm_after_answering(self, conv):
        """After editing one answer, go straight back to CONFIRM — not the next question."""
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("1")  # select Q1 to edit
        assert conv.currentState == "question_0"
        assert conv._editing is True
        await conv.on_message("New A1")  # answer Q1
        assert conv.currentState == SubmitState.CONFIRM
        assert conv._editing is False

    @pytest.mark.asyncio
    async def test_edit_shows_back_to_review_and_leave(self, conv):
        """During edit mode, back (to review) and leave should be available — no reset."""
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("2")  # select Q2 to edit
        sent = conv.user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert BACK_EMOJI in reaction_calls
        assert RESET_EMOJI not in reaction_calls
        assert LEAVE_EMOJI in reaction_calls

    @pytest.mark.asyncio
    async def test_edit_back_returns_to_confirm_without_changing_answer(self, conv):
        """Pressing back during edit returns to review without modifying the answer."""
        q2_id = conv.questions[1][0]
        original_answer = conv.answers[q2_id]
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("2")  # select Q2 to edit
        await conv.on_react(BACK_EMOJI)  # bail out without retyping
        assert conv.currentState == SubmitState.CONFIRM
        assert conv.answers[q2_id] == original_answer
        assert conv._editing is False

    @pytest.mark.asyncio
    async def test_edit_updates_answer_value(self, conv):
        """Editing an answer should actually update the stored value."""
        q1_id = conv.questions[0][0]
        assert conv.answers[q1_id] == "Old A1"
        conv.currentState = SubmitState.EDIT_SELECT
        await conv.repost_state()
        await conv.on_message("1")
        await conv.on_message("Brand new A1")
        assert conv.answers[q1_id] == "Brand new A1"
        assert conv.currentState == SubmitState.CONFIRM


class TestApplicationTemplateCreateConversation:
    """ApplicationTemplateCreateConversation saves questions to ApplicationTemplate."""

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild):
        _make_send_return(mock_user)
        return ApplicationTemplateCreateConversation(
            mock_bot,
            mock_user,
            mock_guild,
            template_name="MyTemplate",
        )

    @pytest.mark.asyncio
    async def test_initial_state_sends_dm(self, conv, mock_user):
        await conv.repost_state()
        mock_user.send.assert_called_once()
        embed = mock_user.send.call_args.kwargs.get("embed") or mock_user.send.call_args[1]["embed"]
        assert "MyTemplate" in embed.title

    @pytest.mark.asyncio
    async def test_saves_template_with_questions(self, conv, mock_user, db_session):
        await conv.repost_state()
        await conv.on_message("Question 1")
        await conv.on_message("Question 2")
        # Go to review, then confirm
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)
        assert conv.currentState == TemplateCreateState.REVIEW
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)

        from models.application import ApplicationTemplate

        tpl = ApplicationTemplate.get_by_name("MyTemplate", conv.guild.id, db_session)
        assert tpl is not None
        assert len(tpl.questions) == 2
        assert tpl.questions[0].QuestionText == "Question 1"

    @pytest.mark.asyncio
    async def test_stores_approval_denial_messages(self, mock_bot, mock_user, mock_guild, db_session):
        _make_send_return(mock_user)
        conv = ApplicationTemplateCreateConversation(
            mock_bot,
            mock_user,
            mock_guild,
            template_name="T2",
            approval_message="Approved!",
            denial_message="Denied!",
        )
        await conv.repost_state()
        await conv.on_message("Q1")
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # review
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # save

        from models.application import ApplicationTemplate

        tpl = ApplicationTemplate.get_by_name("T2", mock_guild.id, db_session)
        assert tpl.ApprovalMessage == "Approved!"
        assert tpl.DenialMessage == "Denied!"

    @pytest.mark.asyncio
    async def test_cancel_with_no_questions_closes(self, conv):
        await conv.repost_state()
        await conv.on_react(CANCEL_EMOJI)
        assert not conv.isActive

    @pytest.mark.asyncio
    async def test_cancel_from_collect_does_not_save(self, conv, mock_user, db_session):
        """Pressing ❌ after adding questions should discard, not save."""
        await conv.repost_state()
        await conv.on_message("Q1")
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        assert not conv.isActive

        from models.application import ApplicationTemplate

        tpl = ApplicationTemplate.get_by_name("MyTemplate", conv.guild.id, db_session)
        assert tpl is None

    @pytest.mark.asyncio
    async def test_cancel_from_review_does_not_save(self, conv, mock_user, db_session):
        """Pressing ❌ on the review screen should discard, not save."""
        await conv.repost_state()
        await conv.on_message("Q1")
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # review
        assert conv.currentState == TemplateCreateState.REVIEW
        _make_send_return(mock_user)
        await conv.on_react(CANCEL_EMOJI)

        assert not conv.isActive

        from models.application import ApplicationTemplate

        tpl = ApplicationTemplate.get_by_name("MyTemplate", conv.guild.id, db_session)
        assert tpl is None

    @pytest.mark.asyncio
    async def test_collect_shows_confirm_and_cancel_reactions(self, conv, mock_user):
        """After adding a question, both ✅ and ❌ reactions should appear."""
        await conv.repost_state()
        _make_send_return(mock_user)
        await conv.on_message("Q1")
        sent = mock_user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert CONFIRM_EMOJI in reaction_calls
        assert CANCEL_EMOJI in reaction_calls

    @pytest.mark.asyncio
    async def test_review_shows_three_reactions(self, conv, mock_user):
        """Review screen should show ✅, ✏️, and ❌."""
        await conv.repost_state()
        await conv.on_message("Q1")
        _make_send_return(mock_user)
        await conv.on_react(CONFIRM_EMOJI)  # → REVIEW
        sent = mock_user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert CONFIRM_EMOJI in reaction_calls
        assert EDIT_EMOJI in reaction_calls
        assert CANCEL_EMOJI in reaction_calls

    @pytest.mark.asyncio
    async def test_review_lists_all_questions(self, conv, mock_user):
        conv.questions = ["Q1", "Q2"]
        conv.currentState = TemplateCreateState.REVIEW
        await conv.repost_state()
        embed = mock_user.send.call_args.kwargs.get("embed") or mock_user.send.call_args[1]["embed"]
        assert "Q1" in embed.description
        assert "Q2" in embed.description

    @pytest.mark.asyncio
    async def test_back_removes_last_question(self, conv, mock_user):
        await conv.repost_state()
        await conv.on_message("Q1")
        await conv.on_message("Q2")
        assert len(conv.questions) == 2
        _make_send_return(mock_user)
        await conv.on_react(BACK_EMOJI)
        assert len(conv.questions) == 1
        assert conv.questions[0] == "Q1"
        assert conv.currentState == TemplateCreateState.COLLECT

    @pytest.mark.asyncio
    async def test_back_on_only_question_returns_to_init(self, conv, mock_user):
        await conv.repost_state()
        await conv.on_message("Q1")
        _make_send_return(mock_user)
        await conv.on_react(BACK_EMOJI)
        assert len(conv.questions) == 0
        assert conv.currentState == TemplateCreateState.INIT

    @pytest.mark.asyncio
    async def test_edit_from_review(self, conv, mock_user):
        """Edit a question from the review screen and return to review."""
        conv.questions = ["OldQ"]
        conv.currentState = TemplateCreateState.REVIEW
        await conv.repost_state()
        _make_send_return(mock_user)
        await conv.on_react(EDIT_EMOJI)
        assert conv.currentState == TemplateCreateState.EDIT_Q_SELECT
        _make_send_return(mock_user)
        await conv.on_message("1")
        assert conv.currentState == TemplateCreateState.EDIT_Q
        _make_send_return(mock_user)
        await conv.on_message("NewQ")
        assert conv.questions[0] == "NewQ"
        assert conv.currentState == TemplateCreateState.REVIEW


class TestApplicationCreateConversationReview:
    """Back button and 3-button final review in admin form creation."""

    @pytest.fixture
    def conv(self, mock_bot, mock_user, mock_guild):
        _make_send_return(mock_user)
        return ApplicationCreateConversation(mock_bot, mock_user, mock_guild, "MyForm", review_channel_id=123)

    @pytest.mark.asyncio
    async def test_confirm_emoji_during_collect_goes_to_review(self, conv):
        await conv.repost_state()  # INIT
        await conv.on_message("Q1")  # COLLECT
        await conv.on_react(CONFIRM_EMOJI)
        assert conv.currentState == CreateState.REVIEW

    @pytest.mark.asyncio
    async def test_back_removes_last_question(self, conv):
        await conv.repost_state()
        await conv.on_message("Q1")
        await conv.on_message("Q2")
        assert len(conv.questions) == 2
        await conv.on_react(BACK_EMOJI)
        assert len(conv.questions) == 1
        assert conv.questions[0] == "Q1"
        assert conv.currentState == CreateState.COLLECT

    @pytest.mark.asyncio
    async def test_back_not_available_on_first_question(self, conv):
        """INIT state (no questions yet) should not offer ⬅️."""
        await conv.repost_state()
        sent = conv.user.send.return_value
        reaction_calls = [str(call.args[0]) for call in sent.add_reaction.call_args_list]
        assert BACK_EMOJI not in reaction_calls

    @pytest.mark.asyncio
    async def test_back_on_only_question_returns_to_init(self, conv):
        """Pressing back when only one question exists should return to INIT, not COLLECT."""
        await conv.repost_state()  # INIT
        await conv.on_message("Q1")  # COLLECT (Q1 added)
        await conv.on_react(BACK_EMOJI)  # BACK → pops Q1 → should go to INIT
        assert len(conv.questions) == 0
        assert conv.currentState == CreateState.INIT

    @pytest.mark.asyncio
    async def test_back_on_only_question_allows_reentry(self, conv):
        """After back from Q1, user can type a new Q1 and proceed normally."""
        await conv.repost_state()
        await conv.on_message("Q1")
        await conv.on_react(BACK_EMOJI)
        # Now back at INIT — type a new question
        await conv.on_message("Q1 revised")
        assert conv.currentState == CreateState.COLLECT
        assert conv.questions == ["Q1 revised"]

    @pytest.mark.asyncio
    async def test_review_with_empty_questions_redirects_to_init(self, conv):
        """If review is somehow reached with no questions, redirect to INIT."""
        conv.questions = []
        conv.currentState = CreateState.REVIEW
        await conv.repost_state()
        assert conv.currentState == CreateState.INIT

    @pytest.mark.asyncio
    async def test_edit_q_select_with_empty_questions_redirects_to_init(self, conv):
        """If edit-question is reached with no questions, redirect to INIT."""
        conv.questions = []
        conv.currentState = CreateState.EDIT_Q_SELECT
        await conv.repost_state()
        assert conv.currentState == CreateState.INIT

    @pytest.mark.asyncio
    async def test_review_lists_all_questions(self, conv):
        conv.questions = ["Q1", "Q2"]
        conv.currentState = CreateState.REVIEW
        await conv.repost_state()
        embed = conv.user.send.call_args.kwargs.get("embed") or conv.user.send.call_args[1]["embed"]
        assert "Q1" in embed.description
        assert "Q2" in embed.description

    @pytest.mark.asyncio
    async def test_review_edit_goes_to_edit_q_select(self, conv):
        conv.questions = ["Q1"]
        conv.currentState = CreateState.REVIEW
        await conv.repost_state()
        await conv.on_react(EDIT_EMOJI)
        assert conv.currentState == CreateState.EDIT_Q_SELECT

    @pytest.mark.asyncio
    async def test_review_cancel_does_not_save(self, conv, db_session):
        conv.questions = ["Q1"]
        conv.currentState = CreateState.REVIEW
        await conv.repost_state()
        await conv.on_react(CANCEL_EMOJI)
        assert not conv.isActive
        from models.application import ApplicationForm

        assert ApplicationForm.get("MyForm", conv.guild.id, db_session) is None

    @pytest.mark.asyncio
    async def test_edit_q_select_valid_number_goes_to_edit_q(self, conv):
        conv.questions = ["Q1", "Q2"]
        conv.currentState = CreateState.EDIT_Q_SELECT
        await conv.repost_state()
        await conv.on_message("1")
        assert conv.currentState == CreateState.EDIT_Q

    @pytest.mark.asyncio
    async def test_edit_q_replaces_question_and_returns_to_review(self, conv):
        conv.questions = ["OldQ"]
        conv._edit_q_index = 0
        conv.currentState = CreateState.EDIT_Q
        await conv.repost_state()
        await conv.on_message("NewQ")
        assert conv.questions[0] == "NewQ"
        assert conv.currentState == CreateState.REVIEW


class TestSubmitConversationRoleMentions:
    """Review embed should mention admin + configured roles in thread, not inline content."""

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
            mock_bot,
            mock_user,
            mock_guild,
            form_id=form.Id,
            form_name="F",
            questions=[(q.Id, "Q1")],
        )

    @pytest.fixture
    def review_channel_with_thread(self):
        """Mock review channel whose sent message has a thread mock attached."""
        thread = MagicMock()
        thread.send = AsyncMock()

        sent_msg = MagicMock()
        sent_msg.id = 777
        sent_msg.create_thread = AsyncMock(return_value=thread)

        channel = MagicMock()
        channel.send = AsyncMock(return_value=sent_msg)
        return channel, thread

    @pytest.mark.asyncio
    async def test_mentions_admin_roles(self, conv, mock_bot, mock_guild, review_channel_with_thread):
        channel, thread = review_channel_with_thread
        admin_role = MagicMock()
        admin_role.id = 888
        admin_role.permissions = MagicMock()
        admin_role.permissions.administrator = True
        admin_role.managed = False
        mock_guild.roles = [admin_role]

        mock_bot.get_channel = MagicMock(return_value=channel)

        conv.answers = {conv.questions[0][0]: "answer"}
        conv.currentState = SubmitState.SUBMIT
        await conv.repost_state()

        # embed posted without content
        call_kwargs = channel.send.call_args.kwargs
        assert "content" not in call_kwargs or call_kwargs.get("content") is None

        # mention sent to thread
        thread.send.assert_called_once()
        assert "<@&888>" in thread.send.call_args.args[0]

    @pytest.mark.asyncio
    async def test_mentions_configured_roles(self, conv, mock_bot, mock_guild, db_session, review_channel_with_thread):
        from models.application import ApplicationGuildRole

        db_session.add(ApplicationGuildRole(GuildId=mock_guild.id, RoleId=111, RoleType="manager"))
        db_session.add(ApplicationGuildRole(GuildId=mock_guild.id, RoleId=222, RoleType="reviewer"))
        db_session.commit()

        mock_guild.roles = []
        channel, thread = review_channel_with_thread
        mock_bot.get_channel = MagicMock(return_value=channel)

        conv.answers = {conv.questions[0][0]: "answer"}
        conv.currentState = SubmitState.SUBMIT
        await conv.repost_state()

        thread.send.assert_called_once()
        mentions = thread.send.call_args.args[0]
        assert "<@&111>" in mentions
        assert "<@&222>" in mentions

    @pytest.mark.asyncio
    async def test_no_thread_send_when_no_roles(self, conv, mock_bot, mock_guild, review_channel_with_thread):
        mock_guild.roles = []

        channel, thread = review_channel_with_thread
        mock_bot.get_channel = MagicMock(return_value=channel)

        conv.answers = {conv.questions[0][0]: "answer"}
        conv.currentState = SubmitState.SUBMIT
        await conv.repost_state()

        # No mentions → thread still created but thread.send not called
        thread.send.assert_not_called()
