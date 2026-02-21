# tests/modules/test_application_view.py
# -*- coding: utf-8 -*-
"""Tests for modules/views/application.py — ApplicationReviewView buttons and modals."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from models.application import (
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationVote,
    SubmissionStatus,
    VoteType,
)
from modules.views.application import (
    ApproveMessageModal,
    ApplicationReviewView,
    DenyReasonModal,
    EditApproveModal,
    EditDenyModal,
    EditVoteSelectView,
    MessageModal,
    OverrideModal,
    VoteSelectView,
    _dm_applicant,
    check_application_permission,
    check_override_permission,
    build_review_embed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GUILD_ID = 987654321
REVIEW_MSG_ID = 777888999
REVIEW_CHANNEL_ID = 100200300
APPLICANT_USER_ID = 111222333
REVIEWER_USER_ID = 444555666


def _seed_form_and_submission(session, *, required_approvals=1, required_denials=1):
    """Insert a form with one question and a pending submission.  Returns (form, submission)."""
    form = ApplicationForm(
        GuildId=GUILD_ID,
        Name="Test Form",
        ReviewChannelId=REVIEW_CHANNEL_ID,
        RequiredApprovals=required_approvals,
        RequiredDenials=required_denials,
    )
    session.add(form)
    session.flush()

    question = ApplicationQuestion(FormId=form.Id, QuestionText="Why do you want to join?", SortOrder=1)
    session.add(question)
    session.flush()

    submission = ApplicationSubmission(
        FormId=form.Id,
        GuildId=GUILD_ID,
        UserId=APPLICANT_USER_ID,
        UserName="Applicant",
        Status="pending",
        SubmittedAt=datetime.now(UTC),
        ReviewMessageId=REVIEW_MSG_ID,
    )
    session.add(submission)
    session.flush()

    answer = ApplicationAnswer(SubmissionId=submission.Id, QuestionId=question.Id, AnswerText="I love this community!")
    session.add(answer)
    session.flush()

    return form, submission


def _make_reviewer_only_interaction(bot, reviewer_role_id):
    """Interaction for a user with ONLY the reviewer role (not manager, not admin)."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.guild.id = GUILD_ID
    interaction.user.guild_permissions.administrator = False
    role = MagicMock()
    role.id = reviewer_role_id
    interaction.user.roles = [role]
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    return interaction


def _make_reviewer_interaction(mock_bot, *, is_admin=True, manager_role_id=None, message_id=REVIEW_MSG_ID):
    """Build a mock Interaction that looks like a reviewer clicking a button."""
    interaction = MagicMock()
    interaction.client = mock_bot
    interaction.user = MagicMock()
    interaction.user.id = REVIEWER_USER_ID
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = is_admin
    interaction.user.roles = []

    if manager_role_id:
        role = MagicMock()
        role.id = manager_role_id
        interaction.user.roles = [role]

    interaction.guild = MagicMock()
    interaction.guild.id = GUILD_ID

    interaction.message = MagicMock()
    interaction.message.id = message_id
    interaction.message.channel = MagicMock()
    interaction.message.channel.id = REVIEW_CHANNEL_ID
    interaction.message.edit = AsyncMock()

    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)

    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    return interaction


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def review_view(mock_bot):
    """Async fixture — discord.ui.View.__init__ needs a running event loop."""
    return ApplicationReviewView(bot=mock_bot)


# ---------------------------------------------------------------------------
# Permission check tests
# ---------------------------------------------------------------------------


class TestPermissionCheck:
    def test_admin_passes(self, mock_bot):
        interaction = _make_reviewer_interaction(mock_bot, is_admin=True)
        assert check_application_permission(interaction, mock_bot) is True

    def test_manager_role_passes(self, mock_bot, db_session):
        manager_role_id = 999888777
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ManagerRoleId=manager_role_id)
        db_session.add(config)
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot, is_admin=False, manager_role_id=manager_role_id)
        assert check_application_permission(interaction, mock_bot) is True

    def test_no_permission_fails(self, mock_bot, db_session):
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)
        assert check_application_permission(interaction, mock_bot) is False

    def test_wrong_role_fails(self, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ManagerRoleId=999888777)
        db_session.add(config)
        db_session.commit()

        # User has a different role
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False, manager_role_id=111111111)
        assert check_application_permission(interaction, mock_bot) is False


# ---------------------------------------------------------------------------
# Approve button tests
# ---------------------------------------------------------------------------


class TestVoteButton:
    @pytest.mark.asyncio
    async def test_vote_sends_select_view(self, review_view, mock_bot, db_session):
        """Vote button should send an ephemeral message containing VoteSelectView."""
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot)

        await review_view.vote.callback(interaction)

        interaction.response.send_message.assert_called_once()
        call_kwargs = interaction.response.send_message.call_args[1]
        assert call_kwargs.get("ephemeral") is True
        assert isinstance(call_kwargs.get("view"), VoteSelectView)

    @pytest.mark.asyncio
    async def test_vote_no_prefill(self, review_view, mock_bot, db_session):
        """Vote modals are never pre-filled — review notes are internal and not tied to applicant messages."""
        form, submission = _seed_form_and_submission(db_session)
        form.ApprovalMessage = "Welcome!"
        form.DenialMessage = "Not this time."
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.vote.callback(interaction)

        view = interaction.response.send_message.call_args[1]["view"]
        assert view.approve_prefill is None
        assert view.deny_prefill is None

    @pytest.mark.asyncio
    async def test_vote_no_permission(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)

        await review_view.vote.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_vote_already_decided(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "denied"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.vote.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "already been decided" in call_args.lower()

    @pytest.mark.asyncio
    async def test_vote_submission_not_found(self, review_view, mock_bot, db_session):
        interaction = _make_reviewer_interaction(mock_bot, message_id=999999999)
        await review_view.vote.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_vote_duplicate_vote_rejected(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        db_session.add(ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote="approve"))
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.vote.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "already voted" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_button_disabled_after_applicant_notified(self, review_view, mock_bot, db_session):
        """Once ApplicantNotified is True on a decided submission, Message is also disabled."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=1)
        submission.Status = "approved"
        submission.ApplicantNotified = True
        db_session.commit()

        # Simulate the embed rebuild triggered by a subsequent button click
        mock_channel = MagicMock()
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)

        from modules.views.application import _update_review_embed

        await _update_review_embed(mock_bot, review_channel_id=REVIEW_CHANNEL_ID, review_message_id=REVIEW_MSG_ID)

        call_kwargs = mock_message.edit.call_args[1]
        view = call_kwargs["view"]
        msg_btn = next(c for c in view.children if c.custom_id == "app_review_message")
        assert msg_btn.disabled is True


# ---------------------------------------------------------------------------
# ApproveMessageModal tests
# ---------------------------------------------------------------------------


class TestApproveMessageModal:
    def _make_mock_channel(self, mock_bot, *, has_thread=True):
        """Return (mock_channel, mock_message, mock_thread) with thread already attached or absent."""
        mock_thread = MagicMock()
        mock_thread.send = AsyncMock()

        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        if has_thread:
            mock_message.thread = mock_thread
        else:
            mock_message.thread = None
            mock_message.create_thread = AsyncMock(return_value=mock_thread)

        mock_channel = MagicMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)

        return mock_channel, mock_message, mock_thread

    @pytest.mark.asyncio
    async def test_approve_modal_records_vote(self, mock_bot, db_session):
        """on_submit records a vote; status stays pending when threshold not reached."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        self._make_mock_channel(mock_bot)

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Looking forward to having you!"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        vote = ApplicationVote.get_user_vote(submission.Id, REVIEWER_USER_ID, db_session)
        assert vote is not None
        assert vote.Vote == "approve"

        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "pending"

    @pytest.mark.asyncio
    async def test_approve_modal_threshold_reached(self, mock_bot, db_session):
        """When threshold is met, submission status becomes approved."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=1)
        self._make_mock_channel(mock_bot)

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Approved!"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "approved"

    @pytest.mark.asyncio
    async def test_approve_modal_posts_to_existing_thread(self, mock_bot, db_session):
        """on_submit posts the reviewer's message with ✅ prefix to an existing thread."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        _, _, mock_thread = self._make_mock_channel(mock_bot, has_thread=True)

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Great application!"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        mock_thread.send.assert_called_once()
        posted = mock_thread.send.call_args[0][0]
        assert "✅" in posted
        assert "Great application!" in posted

    @pytest.mark.asyncio
    async def test_approve_modal_creates_thread_when_none(self, mock_bot, db_session):
        """If no thread exists, on_submit creates one then posts to it."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        _, mock_message, mock_thread = self._make_mock_channel(mock_bot, has_thread=False)

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Welcome!"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        mock_message.create_thread.assert_called_once()
        mock_thread.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_modal_responds_before_editing(self, mock_bot, db_session):
        """defer (the user response) must happen before message.edit (embed rebuild)."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        _, mock_message, _ = self._make_mock_channel(mock_bot)

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Nice!"

        call_order = []
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        interaction.response.defer = AsyncMock(side_effect=lambda *a, **kw: call_order.append("response"))
        mock_message.edit = AsyncMock(side_effect=lambda *a, **kw: call_order.append("edit"))

        await modal.on_submit(interaction)

        assert call_order == ["response", "edit"]

    @pytest.mark.asyncio
    async def test_approve_modal_duplicate_vote_rejected(self, mock_bot, db_session):
        """IntegrityError on flush → followup.send 'already voted'."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        db_session.add(ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote="approve"))
        db_session.commit()

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Vote again!"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        call_args = str(interaction.followup.send.call_args)
        assert "already voted" in call_args.lower()

    @pytest.mark.asyncio
    async def test_approve_modal_disables_vote_button_but_not_message(self, mock_bot, db_session):
        """When approval threshold is reached, Vote is disabled; Message stays enabled."""
        form, submission = _seed_form_and_submission(db_session, required_approvals=1)
        _, mock_message, _ = self._make_mock_channel(mock_bot)

        modal = ApproveMessageModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Congrats!"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        call_kwargs = mock_message.edit.call_args[1]
        view = call_kwargs["view"]
        vote_btn = next(c for c in view.children if c.custom_id == "app_review_vote")
        msg_btn = next(c for c in view.children if c.custom_id == "app_review_message")
        assert vote_btn.disabled is True
        assert msg_btn.disabled is False  # not yet notified


# ---------------------------------------------------------------------------
# VoteSelectView tests
# ---------------------------------------------------------------------------


class TestVoteSelectView:
    @pytest.mark.asyncio
    async def test_select_approve_opens_approve_modal(self, mock_bot, db_session):
        """Selecting 'approve' from the dropdown should open ApproveMessageModal."""
        form, submission = _seed_form_and_submission(db_session)

        view = VoteSelectView(
            submission_id=submission.Id,
            bot=mock_bot,
            approve_prefill="Welcome!",
            deny_prefill="Sorry.",
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )

        interaction = _make_reviewer_interaction(mock_bot)
        view.vote_select._values = ["approve"]
        await view.vote_select.callback(interaction)

        interaction.response.send_modal.assert_called_once()
        modal = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, ApproveMessageModal)
        assert modal.message.default == "Welcome!"

    @pytest.mark.asyncio
    async def test_select_deny_opens_deny_modal(self, mock_bot, db_session):
        """Selecting 'deny' from the dropdown should open DenyReasonModal."""
        form, submission = _seed_form_and_submission(db_session)

        view = VoteSelectView(
            submission_id=submission.Id,
            bot=mock_bot,
            approve_prefill="Welcome!",
            deny_prefill="Sorry.",
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )

        interaction = _make_reviewer_interaction(mock_bot)
        view.vote_select._values = ["deny"]
        await view.vote_select.callback(interaction)

        interaction.response.send_modal.assert_called_once()
        modal = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, DenyReasonModal)
        assert modal.message.default == "Sorry."


# ---------------------------------------------------------------------------
# DenyReasonModal tests
# ---------------------------------------------------------------------------


class TestDenyReasonModal:
    def _make_thread_mocks(self, mock_bot):
        """Return (mock_channel, mock_message, mock_thread) with an attached thread."""
        mock_thread = MagicMock()
        mock_thread.send = AsyncMock()
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_message.thread = mock_thread
        mock_channel = MagicMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)
        return mock_channel, mock_message, mock_thread

    @pytest.mark.asyncio
    async def test_deny_modal_records_vote_and_denies(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_denials=1)
        self._make_thread_mocks(mock_bot)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Not a good fit"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        vote = ApplicationVote.get_user_vote(submission.Id, REVIEWER_USER_ID, db_session)
        assert vote is not None
        assert vote.Vote == "deny"

        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "denied"
        assert refreshed.DecisionReason == "Not a good fit"

    @pytest.mark.asyncio
    async def test_deny_modal_posts_to_thread(self, mock_bot, db_session):
        """on_submit posts the denial message with ❌ prefix to the review thread."""
        form, submission = _seed_form_and_submission(db_session, required_denials=2)
        _, _, mock_thread = self._make_thread_mocks(mock_bot)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Does not meet requirements."

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        mock_thread.send.assert_called_once()
        posted = mock_thread.send.call_args[0][0]
        assert "❌" in posted
        assert "Does not meet requirements." in posted

    @pytest.mark.asyncio
    async def test_deny_modal_responds_before_editing_review(self, mock_bot, db_session):
        """Modal on_submit should respond to the interaction BEFORE editing the review message."""
        form, submission = _seed_form_and_submission(db_session, required_denials=3)
        _, mock_message, _ = self._make_thread_mocks(mock_bot)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Not this time."

        call_order = []
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        interaction.response.defer = AsyncMock(side_effect=lambda *a, **kw: call_order.append("response"))
        mock_message.edit = AsyncMock(side_effect=lambda *a, **kw: call_order.append("edit"))

        await modal.on_submit(interaction)

        assert call_order == ["response", "edit"]

    @pytest.mark.asyncio
    async def test_deny_modal_below_threshold(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_denials=3)
        self._make_thread_mocks(mock_bot)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Not yet."

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "pending"

    @pytest.mark.asyncio
    async def test_deny_modal_submission_already_decided(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "approved"
        db_session.commit()

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Too late"

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        await modal.on_submit(interaction)

        call_args = str(interaction.followup.send.call_args)
        assert "no longer pending" in call_args.lower()


# ---------------------------------------------------------------------------
# Message button tests
# ---------------------------------------------------------------------------


class TestMessageButton:
    @pytest.mark.asyncio
    async def test_message_sends_modal(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot)

        await review_view.message_applicant.callback(interaction)

        interaction.response.send_modal.assert_called_once()
        modal = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, MessageModal)
        assert modal.target_user_id == APPLICANT_USER_ID

    @pytest.mark.asyncio
    async def test_message_no_permission(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)

        await review_view.message_applicant.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_submission_not_found(self, review_view, mock_bot, db_session):
        interaction = _make_reviewer_interaction(mock_bot, message_id=999999999)
        await review_view.message_applicant.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_button_prefills_approval_message(self, review_view, mock_bot, db_session):
        """When the submission is approved and a default message is configured, pre-fill the modal."""
        form, submission = _seed_form_and_submission(db_session)
        form.ApprovalMessage = "Welcome to the team!"
        submission.Status = "approved"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.message_applicant.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.message.default == "Welcome to the team!"

    @pytest.mark.asyncio
    async def test_message_button_no_prefill_when_pending(self, review_view, mock_bot, db_session):
        """When the submission is still pending, the modal message field is not pre-filled."""
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot)

        await review_view.message_applicant.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.message.default is None

    @pytest.mark.asyncio
    async def test_message_button_uses_default_approval_message_when_none_configured(
        self, review_view, mock_bot, db_session
    ):
        """Approved submission without a configured ApprovalMessage: fall back to the default string."""
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "approved"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.message_applicant.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.message.default is not None
        assert "approved" in modal.message.default.lower()

    @pytest.mark.asyncio
    async def test_message_button_uses_default_denial_message_when_none_configured(
        self, review_view, mock_bot, db_session
    ):
        """Denied submission without a configured DenialMessage: fall back to the default string."""
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "denied"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.message_applicant.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.message.default is not None
        assert "denied" in modal.message.default.lower()

    @pytest.mark.asyncio
    async def test_message_button_prefills_denial_message(self, review_view, mock_bot, db_session):
        """When the submission is denied and a default denial message is configured, pre-fill the modal."""
        form, submission = _seed_form_and_submission(db_session)
        form.DenialMessage = "Unfortunately you do not meet our requirements."
        submission.Status = "denied"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.message_applicant.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.message.default == "Unfortunately you do not meet our requirements."


# ---------------------------------------------------------------------------
# MessageModal tests
# ---------------------------------------------------------------------------


class TestMessageModal:
    @pytest.mark.asyncio
    async def test_message_modal_sends_dm(self, mock_bot):
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user = AsyncMock(return_value=mock_user)

        modal = MessageModal(user_id=APPLICANT_USER_ID, bot=mock_bot)
        modal.message._value = "Please provide more details about your experience."

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        mock_user.send.assert_called_once()
        call_args = str(interaction.response.send_message.call_args)
        assert "message sent" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_modal_dm_forbidden(self, mock_bot):
        mock_bot.fetch_user = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot send messages"))

        modal = MessageModal(user_id=APPLICANT_USER_ID, bot=mock_bot)
        modal.message._value = "Hello"

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "could not dm" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_modal_dm_not_found(self, mock_bot):
        """NotFound should be handled the same as Forbidden (user deleted account)."""
        mock_bot.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "Unknown User"))

        modal = MessageModal(user_id=APPLICANT_USER_ID, bot=mock_bot)
        modal.message._value = "Hello"

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "could not dm" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_modal_empty_skips_dm(self, mock_bot):
        """Submitting the modal with an empty message should not DM the applicant."""
        mock_bot.fetch_user = AsyncMock()

        modal = MessageModal(user_id=APPLICANT_USER_ID, bot=mock_bot)
        modal.message._value = ""

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        mock_bot.fetch_user.assert_not_called()
        call_args = str(interaction.response.send_message.call_args)
        assert "no message sent" in call_args.lower()

    @pytest.mark.asyncio
    async def test_message_modal_prefill_stored(self, mock_bot):
        """Prefill string should be set as the TextInput default."""
        modal = MessageModal(user_id=APPLICANT_USER_ID, bot=mock_bot, prefill="Welcome aboard!")
        assert modal.message.default == "Welcome aboard!"

    @pytest.mark.asyncio
    async def test_message_modal_sets_notified_on_decided_submission(self, mock_bot, db_session):
        """Successful DM on a decided submission must flip ApplicantNotified to True."""
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "approved"
        db_session.commit()

        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user = AsyncMock(return_value=mock_user)

        mock_channel = MagicMock()
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)

        modal = MessageModal(
            user_id=APPLICANT_USER_ID,
            bot=mock_bot,
            submission_id=submission.Id,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.message._value = "Congratulations!"

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        refreshed = db_session.get(type(submission), submission.Id)
        assert refreshed.ApplicantNotified is True

    @pytest.mark.asyncio
    async def test_message_modal_does_not_set_notified_on_pending_submission(self, mock_bot, db_session):
        """Successful DM while submission is still pending must not set ApplicantNotified."""
        form, submission = _seed_form_and_submission(db_session)

        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user = AsyncMock(return_value=mock_user)

        modal = MessageModal(
            user_id=APPLICANT_USER_ID,
            bot=mock_bot,
            submission_id=submission.Id,
        )
        modal.message._value = "Could you clarify your experience?"

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        refreshed = db_session.get(type(submission), submission.Id)
        assert refreshed.ApplicantNotified is False

    @pytest.mark.asyncio
    async def test_message_modal_failed_dm_does_not_set_notified(self, mock_bot, db_session):
        """If the DM fails, ApplicantNotified must stay False."""
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "approved"
        db_session.commit()

        mock_bot.fetch_user = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot DM"))

        modal = MessageModal(
            user_id=APPLICANT_USER_ID,
            bot=mock_bot,
            submission_id=submission.Id,
        )
        modal.message._value = "Welcome!"

        interaction = _make_reviewer_interaction(mock_bot)
        await modal.on_submit(interaction)

        refreshed = db_session.get(type(submission), submission.Id)
        assert refreshed.ApplicantNotified is False


# ---------------------------------------------------------------------------
# _dm_applicant tests
# ---------------------------------------------------------------------------


class TestDmApplicant:
    @pytest.mark.asyncio
    async def test_dm_applicant_forbidden(self, mock_bot):
        """Forbidden should be silently logged."""
        mock_bot.fetch_user = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Cannot send messages"))
        embed = discord.Embed(title="Test")

        await _dm_applicant(mock_bot, APPLICANT_USER_ID, embed)

        mock_bot.log.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_applicant_not_found(self, mock_bot):
        """NotFound should be silently logged (user deleted their account)."""
        mock_bot.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "Unknown User"))
        embed = discord.Embed(title="Test")

        await _dm_applicant(mock_bot, APPLICANT_USER_ID, embed)

        mock_bot.log.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_applicant_success(self, mock_bot):
        """Successful DM should not log a warning."""
        mock_user = MagicMock()
        mock_user.send = AsyncMock()
        mock_bot.fetch_user = AsyncMock(return_value=mock_user)
        embed = discord.Embed(title="Test")

        await _dm_applicant(mock_bot, APPLICANT_USER_ID, embed)

        mock_user.send.assert_called_once_with(embed=embed)
        mock_bot.log.warning.assert_not_called()


# ---------------------------------------------------------------------------
# build_review_embed tests
# ---------------------------------------------------------------------------


class TestBuildReviewEmbed:
    def test_embed_contains_applicant_and_qa(self, db_session):
        form, submission = _seed_form_and_submission(db_session)
        embed = build_review_embed(submission, form, db_session)

        assert form.Name in embed.title
        # Check that the applicant user ID is in one of the fields
        field_values = [f.value for f in embed.fields]
        assert any(str(APPLICANT_USER_ID) in v for v in field_values)
        # Check Q&A field
        field_names = [f.name for f in embed.fields]
        assert any("Why do you want to join?" in n for n in field_names)

    def test_embed_footer_shows_counts(self, db_session):
        form, submission = _seed_form_and_submission(db_session, required_approvals=3, required_denials=2)
        embed = build_review_embed(submission, form, db_session)

        assert "Approvals: 0/3" in embed.footer.text
        assert "Denials: 0/2" in embed.footer.text

    def test_naive_submitted_at_is_normalized(self, db_session):
        """SQLite strips tzinfo; build_review_embed should re-attach UTC before calling format_dt."""
        form, submission = _seed_form_and_submission(db_session)
        # Simulate what SQLite does: strip the tzinfo from the stored datetime.
        submission.SubmittedAt = submission.SubmittedAt.replace(tzinfo=None)

        # Should not raise — the guard must fire before discord.utils.format_dt.
        embed = build_review_embed(submission, form, db_session)

        submitted_field = next((f for f in embed.fields if f.name == "Submitted"), None)
        assert submitted_field is not None
        # discord.utils.format_dt returns a <t:TIMESTAMP:style> string.
        assert submitted_field.value.startswith("<t:")


# ---------------------------------------------------------------------------
# View structure tests
# ---------------------------------------------------------------------------


class TestReviewViewStructure:
    @pytest.mark.asyncio
    async def test_view_has_vote_and_message_buttons(self):
        """Persistent review view should have Vote, Edit Vote, Message, and Override buttons."""
        view = ApplicationReviewView(bot=None)
        custom_ids = {c.custom_id for c in view.children}
        assert "app_review_vote" in custom_ids
        assert "app_review_edit_vote" in custom_ids
        assert "app_review_message" in custom_ids
        assert "app_review_override" in custom_ids
        assert "app_review_approve" not in custom_ids
        assert "app_review_deny" not in custom_ids


# ---------------------------------------------------------------------------
# Override permission tests
# ---------------------------------------------------------------------------


class TestOverridePermission:
    def test_admin_can_override(self, mock_bot, db_session):
        interaction = _make_reviewer_interaction(mock_bot, is_admin=True)
        assert check_override_permission(interaction, mock_bot) is True

    def test_manager_role_can_override(self, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ManagerRoleId=777)
        db_session.add(config)
        db_session.commit()
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False, manager_role_id=777)
        assert check_override_permission(interaction, mock_bot) is True

    def test_reviewer_role_cannot_override(self, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ReviewerRoleId=888)
        db_session.add(config)
        db_session.commit()
        interaction = _make_reviewer_only_interaction(mock_bot, reviewer_role_id=888)
        assert check_override_permission(interaction, mock_bot) is False

    def test_no_role_cannot_override(self, mock_bot, db_session):
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)
        assert check_override_permission(interaction, mock_bot) is False


# ---------------------------------------------------------------------------
# Reviewer role permission tests
# ---------------------------------------------------------------------------


class TestReviewerRolePermission:
    def test_reviewer_role_can_vote(self, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ReviewerRoleId=888)
        db_session.add(config)
        db_session.commit()
        interaction = _make_reviewer_only_interaction(mock_bot, reviewer_role_id=888)
        assert check_application_permission(interaction, mock_bot) is True

    def test_wrong_reviewer_role_fails(self, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ReviewerRoleId=888)
        db_session.add(config)
        db_session.commit()
        interaction = _make_reviewer_only_interaction(mock_bot, reviewer_role_id=999)
        assert check_application_permission(interaction, mock_bot) is False


# ---------------------------------------------------------------------------
# EditVoteSelectView tests
# ---------------------------------------------------------------------------


class TestEditVoteSelectView:
    @pytest.mark.asyncio
    async def test_approve_current_vote_sets_default(self, mock_bot):
        view = EditVoteSelectView(
            submission_id=1,
            bot=mock_bot,
            current_vote=VoteType.APPROVE,
            review_channel_id=111,
            review_message_id=222,
        )
        approve_opt = next(o for o in view.vote_select.options if o.value == "approve")
        deny_opt = next(o for o in view.vote_select.options if o.value == "deny")
        assert approve_opt.default is True
        assert deny_opt.default is False

    @pytest.mark.asyncio
    async def test_deny_current_vote_sets_default(self, mock_bot):
        view = EditVoteSelectView(
            submission_id=1,
            bot=mock_bot,
            current_vote=VoteType.DENY,
            review_channel_id=111,
            review_message_id=222,
        )
        approve_opt = next(o for o in view.vote_select.options if o.value == "approve")
        deny_opt = next(o for o in view.vote_select.options if o.value == "deny")
        assert approve_opt.default is False
        assert deny_opt.default is True

    @pytest.mark.asyncio
    async def test_selecting_same_vote_returns_error(self, mock_bot):
        view = EditVoteSelectView(
            submission_id=1,
            bot=mock_bot,
            current_vote=VoteType.APPROVE,
            review_channel_id=111,
            review_message_id=222,
        )
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        view.vote_select._values = ["approve"]  # same as current
        await view.vote_select.callback(interaction)
        interaction.response.send_message.assert_called_once()
        msg = str(interaction.response.send_message.call_args).lower()
        assert "same" in msg or "already" in msg

    @pytest.mark.asyncio
    async def test_selecting_approve_opens_edit_approve_modal(self, mock_bot):
        view = EditVoteSelectView(
            submission_id=1,
            bot=mock_bot,
            current_vote=VoteType.DENY,
            review_channel_id=111,
            review_message_id=222,
        )
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        view.vote_select._values = ["approve"]
        await view.vote_select.callback(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], EditApproveModal)

    @pytest.mark.asyncio
    async def test_selecting_deny_opens_edit_deny_modal(self, mock_bot):
        view = EditVoteSelectView(
            submission_id=1,
            bot=mock_bot,
            current_vote=VoteType.APPROVE,
            review_channel_id=111,
            review_message_id=222,
        )
        interaction = MagicMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        view.vote_select._values = ["deny"]
        await view.vote_select.callback(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], EditDenyModal)


# ---------------------------------------------------------------------------
# EditApproveModal tests
# ---------------------------------------------------------------------------


class TestEditApproveModal:
    def _make_thread_mock(self, mock_bot):
        mock_thread = AsyncMock()
        mock_bot.get_channel.return_value = AsyncMock(
            fetch_message=AsyncMock(return_value=AsyncMock(thread=mock_thread))
        )
        return mock_thread

    @pytest.mark.asyncio
    async def test_changes_vote_from_deny_to_approve(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        vote = ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote=VoteType.DENY)
        db_session.add(vote)
        db_session.commit()
        self._make_thread_mock(mock_bot)

        modal = EditApproveModal(
            submission_id=submission.Id,
            bot=mock_bot,
            previous_vote=VoteType.DENY,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.message._value = "Looks good after all"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        with mock_bot.session_scope() as session:
            new_vote = ApplicationVote.get_user_vote(submission.Id, REVIEWER_USER_ID, session)
        assert new_vote.Vote == VoteType.APPROVE

    @pytest.mark.asyncio
    async def test_thread_message_has_change_emojis(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        vote = ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote=VoteType.DENY)
        db_session.add(vote)
        db_session.commit()
        mock_thread = self._make_thread_mock(mock_bot)

        modal = EditApproveModal(
            submission_id=submission.Id,
            bot=mock_bot,
            previous_vote=VoteType.DENY,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.message._value = "changed mind"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        thread_msg = mock_thread.send.call_args[0][0]
        assert "🔄" in thread_msg
        assert "❌" in thread_msg  # previous deny
        assert "✅" in thread_msg  # new approve

    @pytest.mark.asyncio
    async def test_threshold_reached_sets_approved(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        vote = ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote=VoteType.DENY)
        db_session.add(vote)
        db_session.commit()
        self._make_thread_mock(mock_bot)

        modal = EditApproveModal(
            submission_id=submission.Id,
            bot=mock_bot,
            previous_vote=VoteType.DENY,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.message._value = "on second thought, yes"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        with mock_bot.session_scope() as session:
            sub = ApplicationSubmission.get_by_id(submission.Id, session)
        assert sub.Status == SubmissionStatus.APPROVED

    @pytest.mark.asyncio
    async def test_not_pending_aborts(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.APPROVED
        db_session.commit()

        modal = EditApproveModal(
            submission_id=submission.Id,
            bot=mock_bot,
            previous_vote=VoteType.DENY,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.message._value = "some note"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        msg = str(interaction.followup.send.call_args).lower()
        assert "pending" in msg or "decided" in msg


# ---------------------------------------------------------------------------
# EditDenyModal tests
# ---------------------------------------------------------------------------


class TestEditDenyModal:
    def _make_thread_mock(self, mock_bot):
        mock_thread = AsyncMock()
        mock_bot.get_channel.return_value = AsyncMock(
            fetch_message=AsyncMock(return_value=AsyncMock(thread=mock_thread))
        )
        return mock_thread

    @pytest.mark.asyncio
    async def test_changes_vote_from_approve_to_deny(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        vote = ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote=VoteType.APPROVE)
        db_session.add(vote)
        db_session.commit()
        self._make_thread_mock(mock_bot)

        modal = EditDenyModal(
            submission_id=submission.Id,
            bot=mock_bot,
            previous_vote=VoteType.APPROVE,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.message._value = "actually not good"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        with mock_bot.session_scope() as session:
            new_vote = ApplicationVote.get_user_vote(submission.Id, REVIEWER_USER_ID, session)
        assert new_vote.Vote == VoteType.DENY

    @pytest.mark.asyncio
    async def test_thread_message_has_change_emojis(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        vote = ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote=VoteType.APPROVE)
        db_session.add(vote)
        db_session.commit()
        mock_thread = self._make_thread_mock(mock_bot)

        modal = EditDenyModal(
            submission_id=submission.Id,
            bot=mock_bot,
            previous_vote=VoteType.APPROVE,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.message._value = "nope"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        thread_msg = mock_thread.send.call_args[0][0]
        assert "🔄" in thread_msg
        assert "✅" in thread_msg  # previous approve
        assert "❌" in thread_msg  # new deny


# ---------------------------------------------------------------------------
# Edit Vote button tests
# ---------------------------------------------------------------------------


class TestEditVoteButton:
    @pytest.mark.asyncio
    async def test_sends_edit_select_view_with_current_vote(self, review_view, mock_bot, db_session):
        """When reviewer has voted, Edit Vote sends EditVoteSelectView with their current vote."""
        form, submission = _seed_form_and_submission(db_session)
        vote = ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote=VoteType.APPROVE)
        db_session.add(vote)
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.edit_vote.callback(interaction)

        call_kwargs = interaction.response.send_message.call_args[1]
        assert call_kwargs.get("ephemeral") is True
        assert isinstance(call_kwargs.get("view"), EditVoteSelectView)
        assert call_kwargs["view"].current_vote == VoteType.APPROVE

    @pytest.mark.asyncio
    async def test_no_prior_vote_sends_message(self, review_view, mock_bot, db_session):
        """If reviewer has not yet voted, Edit Vote should explain and point to Vote button."""
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.edit_vote.callback(interaction)

        msg = str(interaction.response.send_message.call_args).lower()
        assert "vote button" in msg or "haven't voted" in msg

    @pytest.mark.asyncio
    async def test_no_permission_rejected(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)
        await review_view.edit_vote.callback(interaction)

        msg = str(interaction.response.send_message.call_args).lower()
        assert "permission" in msg

    @pytest.mark.asyncio
    async def test_not_pending_rejected(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.APPROVED
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.edit_vote.callback(interaction)

        msg = str(interaction.response.send_message.call_args).lower()
        assert "decided" in msg or "pending" in msg


# ---------------------------------------------------------------------------
# OverrideModal tests
# ---------------------------------------------------------------------------


class TestOverrideModal:
    def _make_thread_mock(self, mock_bot):
        mock_thread = AsyncMock()
        mock_bot.get_channel.return_value = AsyncMock(
            fetch_message=AsyncMock(return_value=AsyncMock(thread=mock_thread))
        )
        return mock_thread

    @pytest.mark.asyncio
    async def test_modal_title_approved_to_denied(self, mock_bot):
        modal = OverrideModal(
            current_status=SubmissionStatus.APPROVED,
            submission_id=1,
            bot=mock_bot,
            review_channel_id=0,
            review_message_id=0,
        )
        assert "Approved" in modal.title
        assert "Denied" in modal.title

    @pytest.mark.asyncio
    async def test_modal_title_denied_to_approved(self, mock_bot):
        modal = OverrideModal(
            current_status=SubmissionStatus.DENIED,
            submission_id=1,
            bot=mock_bot,
            review_channel_id=0,
            review_message_id=0,
        )
        assert "Denied" in modal.title
        assert "Approved" in modal.title

    @pytest.mark.asyncio
    async def test_flips_approved_to_denied(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.APPROVED
        db_session.commit()
        self._make_thread_mock(mock_bot)

        modal = OverrideModal(
            current_status=SubmissionStatus.APPROVED,
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.reason._value = "Changed due to new info"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        with mock_bot.session_scope() as session:
            sub = ApplicationSubmission.get_by_id(submission.Id, session)
        assert sub.Status == SubmissionStatus.DENIED

    @pytest.mark.asyncio
    async def test_flips_denied_to_approved(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.DENIED
        db_session.commit()
        self._make_thread_mock(mock_bot)

        modal = OverrideModal(
            current_status=SubmissionStatus.DENIED,
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.reason._value = "Actually looks fine"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        with mock_bot.session_scope() as session:
            sub = ApplicationSubmission.get_by_id(submission.Id, session)
        assert sub.Status == SubmissionStatus.APPROVED

    @pytest.mark.asyncio
    async def test_thread_message_contains_override_info(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.APPROVED
        db_session.commit()
        mock_thread = self._make_thread_mock(mock_bot)

        modal = OverrideModal(
            current_status=SubmissionStatus.APPROVED,
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=111,
            review_message_id=222,
        )
        modal.reason._value = "Override reason here"
        interaction = _make_reviewer_interaction(mock_bot)
        interaction.followup = AsyncMock()
        await modal.on_submit(interaction)

        thread_msg = mock_thread.send.call_args[0][0]
        assert "🔄" in thread_msg
        assert "approved" in thread_msg.lower()
        assert "denied" in thread_msg.lower()
        assert "Override reason here" in thread_msg


# ---------------------------------------------------------------------------
# Override button tests
# ---------------------------------------------------------------------------


class TestOverrideButton:
    @pytest.mark.asyncio
    async def test_admin_opens_override_modal(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.APPROVED
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot, is_admin=True)
        await review_view.override.callback(interaction)

        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], OverrideModal)

    @pytest.mark.asyncio
    async def test_manager_role_opens_override_modal(self, review_view, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ManagerRoleId=REVIEWER_USER_ID)
        db_session.add(config)
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.DENIED
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot, is_admin=False, manager_role_id=REVIEWER_USER_ID)
        await review_view.override.callback(interaction)

        interaction.response.send_modal.assert_called_once()

    @pytest.mark.asyncio
    async def test_reviewer_role_cannot_override(self, review_view, mock_bot, db_session):
        config = ApplicationGuildConfig(GuildId=GUILD_ID, ReviewerRoleId=888)
        db_session.add(config)
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.APPROVED
        db_session.commit()

        interaction = _make_reviewer_only_interaction(mock_bot, reviewer_role_id=888)
        await review_view.override.callback(interaction)

        msg = str(interaction.response.send_message.call_args).lower()
        assert "permission" in msg

    @pytest.mark.asyncio
    async def test_pending_submission_rejected(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot, is_admin=True)
        await review_view.override.callback(interaction)

        msg = str(interaction.response.send_message.call_args).lower()
        assert "pending" in msg

    @pytest.mark.asyncio
    async def test_modal_receives_correct_flip_direction(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = SubmissionStatus.DENIED
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot, is_admin=True)
        await review_view.override.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.current_status == SubmissionStatus.DENIED
        assert modal.new_status == SubmissionStatus.APPROVED
