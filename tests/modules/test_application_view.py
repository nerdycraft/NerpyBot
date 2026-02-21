# tests/modules/test_application_view.py
# -*- coding: utf-8 -*-
"""Tests for modules/views/application.py — ApplicationReviewView buttons and modals."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from models.application import (
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationVote,
)
from modules.views.application import (
    ApplicationReviewView,
    DenyReasonModal,
    MessageModal,
    check_application_permission,
    _dm_applicant,
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


class TestApproveButton:
    @pytest.mark.asyncio
    async def test_approve_records_vote(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)
        interaction = _make_reviewer_interaction(mock_bot)

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock):
            await review_view.approve.callback(interaction)

        vote = ApplicationVote.get_user_vote(submission.Id, REVIEWER_USER_ID, db_session)
        assert vote is not None
        assert vote.Vote == "approve"

    @pytest.mark.asyncio
    async def test_approve_duplicate_vote_rejected(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_approvals=2)

        # Pre-existing vote
        db_session.add(ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote="approve"))
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.approve.callback(interaction)

        call_args = str(interaction.followup.send.call_args)
        assert "already voted" in call_args.lower()

    @pytest.mark.asyncio
    async def test_approve_threshold_reached(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_approvals=1)
        interaction = _make_reviewer_interaction(mock_bot)

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock) as mock_dm:
            await review_view.approve.callback(interaction)

        # Submission should now be approved
        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "approved"
        mock_dm.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_no_permission(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)

        await review_view.approve.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_approve_already_decided(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "denied"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.approve.callback(interaction)

        call_args = str(interaction.followup.send.call_args)
        assert "already been decided" in call_args.lower()

    @pytest.mark.asyncio
    async def test_approve_submission_not_found(self, review_view, mock_bot, db_session):
        interaction = _make_reviewer_interaction(mock_bot, message_id=999999999)
        await review_view.approve.callback(interaction)

        call_args = str(interaction.followup.send.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_approve_responds_before_editing_review(self, review_view, mock_bot, db_session):
        """Approve should respond to the interaction BEFORE editing the review message."""
        _seed_form_and_submission(db_session, required_approvals=2)
        interaction = _make_reviewer_interaction(mock_bot)

        call_order = []

        async def track_defer(*args, **kwargs):
            call_order.append("response")

        async def track_edit(*args, **kwargs):
            call_order.append("edit")

        interaction.response.defer = AsyncMock(side_effect=track_defer)
        interaction.message.edit = AsyncMock(side_effect=track_edit)

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock):
            await review_view.approve.callback(interaction)

        assert call_order == ["response", "edit"]

    @pytest.mark.asyncio
    async def test_approve_updates_embed_with_vote_counts(self, review_view, mock_bot, db_session):
        """After approving, the review embed should be updated with vote count labels."""
        _seed_form_and_submission(db_session, required_approvals=3)
        interaction = _make_reviewer_interaction(mock_bot)

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock):
            await review_view.approve.callback(interaction)

        # The message.edit call should have a view with updated labels
        interaction.message.edit.assert_called_once()
        call_kwargs = interaction.message.edit.call_args[1]
        view = call_kwargs["view"]
        approve_btn = next(c for c in view.children if c.custom_id == "app_review_approve")
        deny_btn = next(c for c in view.children if c.custom_id == "app_review_deny")
        assert "1/3" in approve_btn.label
        assert "0/1" in deny_btn.label


# ---------------------------------------------------------------------------
# Deny button tests
# ---------------------------------------------------------------------------


class TestDenyButton:
    @pytest.mark.asyncio
    async def test_deny_sends_modal(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot)

        await review_view.deny.callback(interaction)

        interaction.response.send_modal.assert_called_once()
        modal = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, DenyReasonModal)

    @pytest.mark.asyncio
    async def test_deny_modal_receives_message_coordinates(self, review_view, mock_bot, db_session):
        """The DenyReasonModal should receive the review message channel and message IDs."""
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot)

        await review_view.deny.callback(interaction)

        modal = interaction.response.send_modal.call_args[0][0]
        assert modal.review_channel_id == REVIEW_CHANNEL_ID
        assert modal.review_message_id == REVIEW_MSG_ID

    @pytest.mark.asyncio
    async def test_deny_duplicate_vote_rejected(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)

        db_session.add(ApplicationVote(SubmissionId=submission.Id, UserId=REVIEWER_USER_ID, Vote="deny"))
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.deny.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "already voted" in call_args.lower()

    @pytest.mark.asyncio
    async def test_deny_no_permission(self, review_view, mock_bot, db_session):
        _seed_form_and_submission(db_session)
        interaction = _make_reviewer_interaction(mock_bot, is_admin=False)

        await review_view.deny.callback(interaction)

        call_args = str(interaction.response.send_message.call_args)
        assert "permission" in call_args.lower()

    @pytest.mark.asyncio
    async def test_deny_already_decided(self, review_view, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session)
        submission.Status = "approved"
        db_session.commit()

        interaction = _make_reviewer_interaction(mock_bot)
        await review_view.deny.callback(interaction)

        # Should reject without opening the modal
        interaction.response.send_modal.assert_not_called()
        call_args = str(interaction.response.send_message.call_args)
        assert "already been decided" in call_args.lower()


# ---------------------------------------------------------------------------
# DenyReasonModal tests
# ---------------------------------------------------------------------------


class TestDenyReasonModal:
    @pytest.mark.asyncio
    async def test_deny_modal_records_vote_and_denies(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_denials=1)

        mock_channel = MagicMock()
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.reason._value = "Not a good fit"

        interaction = _make_reviewer_interaction(mock_bot)
        # Modal interactions do NOT have interaction.message
        interaction.message = None

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock) as mock_dm:
            await modal.on_submit(interaction)

        vote = ApplicationVote.get_user_vote(submission.Id, REVIEWER_USER_ID, db_session)
        assert vote is not None
        assert vote.Vote == "deny"

        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "denied"
        assert refreshed.DecisionReason == "Not a good fit"
        mock_dm.assert_called_once()

    @pytest.mark.asyncio
    async def test_deny_modal_responds_before_editing_review(self, mock_bot, db_session):
        """Modal on_submit should respond to the interaction BEFORE editing the review message."""
        form, submission = _seed_form_and_submission(db_session, required_denials=3)

        mock_channel = MagicMock()
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.reason._value = ""

        call_order = []

        async def track_defer(*args, **kwargs):
            call_order.append("response")

        async def track_edit(*args, **kwargs):
            call_order.append("edit")

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None
        interaction.response.defer = AsyncMock(side_effect=track_defer)
        mock_message.edit = AsyncMock(side_effect=track_edit)

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock):
            await modal.on_submit(interaction)

        assert call_order == ["response", "edit"]

    @pytest.mark.asyncio
    async def test_deny_modal_below_threshold(self, mock_bot, db_session):
        form, submission = _seed_form_and_submission(db_session, required_denials=3)

        mock_channel = MagicMock()
        mock_message = MagicMock()
        mock_message.edit = AsyncMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        mock_bot.get_channel = MagicMock(return_value=mock_channel)

        modal = DenyReasonModal(
            submission_id=submission.Id,
            bot=mock_bot,
            review_channel_id=REVIEW_CHANNEL_ID,
            review_message_id=REVIEW_MSG_ID,
        )
        modal.reason._value = ""

        interaction = _make_reviewer_interaction(mock_bot)
        interaction.message = None

        with patch("modules.views.application._dm_applicant", new_callable=AsyncMock) as mock_dm:
            await modal.on_submit(interaction)

        # Should still be pending
        refreshed = ApplicationSubmission.get_by_id(submission.Id, db_session)
        assert refreshed.Status == "pending"
        mock_dm.assert_not_called()

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
        modal.reason._value = "Too late"

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
# Vote count label tests
# ---------------------------------------------------------------------------


class TestVoteCountLabels:
    @pytest.mark.asyncio
    async def test_default_labels(self):
        """Persistent registration uses plain labels without counts."""
        view = ApplicationReviewView(bot=None)
        approve_btn = next(c for c in view.children if c.custom_id == "app_review_approve")
        deny_btn = next(c for c in view.children if c.custom_id == "app_review_deny")
        assert approve_btn.label == "Approve"
        assert deny_btn.label == "Deny"

    @pytest.mark.asyncio
    async def test_custom_labels_with_counts(self):
        """When vote counts are passed, labels should reflect them."""
        view = ApplicationReviewView(bot=None, approve_label="Approve (2/3)", deny_label="Deny (1/2)")
        approve_btn = next(c for c in view.children if c.custom_id == "app_review_approve")
        deny_btn = next(c for c in view.children if c.custom_id == "app_review_deny")
        assert approve_btn.label == "Approve (2/3)"
        assert deny_btn.label == "Deny (1/2)"
