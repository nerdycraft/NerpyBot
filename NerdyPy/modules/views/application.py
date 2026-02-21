# -*- coding: utf-8 -*-
"""Persistent discord.ui views and modals for the application review system.

ApplicationReviewView — four-button view (Vote / Edit Vote / Message / Override) attached to
review embeds in the review channel.  Uses ``timeout=None`` and fixed ``custom_id``
strings so the view survives bot restarts.
"""

from datetime import UTC

import discord
from sqlalchemy.exc import IntegrityError

from models.application import (
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationSubmission,
    ApplicationVote,
    SubmissionStatus,
    VoteType,
)


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------


def check_application_permission(interaction: discord.Interaction, bot) -> bool:
    """Return True if the user is a guild administrator or holds the manager or reviewer role."""
    if interaction.user.guild_permissions.administrator:
        return True
    with bot.session_scope() as session:
        config = ApplicationGuildConfig.get(interaction.guild.id, session)
        if config:
            if config.ManagerRoleId and any(r.id == config.ManagerRoleId for r in interaction.user.roles):
                return True
            if config.ReviewerRoleId and any(r.id == config.ReviewerRoleId for r in interaction.user.roles):
                return True
    return False


def check_override_permission(interaction: discord.Interaction, bot) -> bool:
    """Return True if the user is a guild administrator or holds the manager role.

    Reviewer role holders are NOT allowed to override decisions.
    """
    if interaction.user.guild_permissions.administrator:
        return True
    with bot.session_scope() as session:
        config = ApplicationGuildConfig.get(interaction.guild.id, session)
        if config and config.ManagerRoleId:
            return any(r.id == config.ManagerRoleId for r in interaction.user.roles)
    return False


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


def build_review_embed(submission, form, session) -> discord.Embed:
    """Build the review embed shown in the review channel for a submission."""
    approve_count = ApplicationVote.count_by_type(submission.Id, VoteType.APPROVE, session)
    deny_count = ApplicationVote.count_by_type(submission.Id, VoteType.DENY, session)

    embed = discord.Embed(title=f"\U0001f4cb {form.Name}", colour=_status_colour(submission.Status))
    embed.add_field(name="Applicant", value=f"<@{submission.UserId}> ({submission.UserName})", inline=True)
    submitted_at = submission.SubmittedAt
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=UTC)
    embed.add_field(name="Submitted", value=discord.utils.format_dt(submitted_at, style="R"), inline=True)

    for answer in submission.answers:
        label = answer.question.QuestionText if answer.question else f"Question {answer.QuestionId}"
        embed.add_field(name=label, value=answer.AnswerText or "_No answer_", inline=False)

    status_display = submission.Status.capitalize()
    embed.set_footer(
        text=(
            f"Status: {status_display} | "
            f"Approvals: {approve_count}/{form.RequiredApprovals} | "
            f"Denials: {deny_count}/{form.RequiredDenials}"
        )
    )
    return embed


async def _update_review_embed(
    bot,
    *,
    interaction: discord.Interaction | None = None,
    review_channel_id: int | None = None,
    review_message_id: int | None = None,
):
    """Rebuild and edit the review embed with current vote counts.

    Can be called either with an ``interaction`` (button callbacks where
    ``interaction.message`` is the review embed) or with explicit
    ``review_channel_id`` / ``review_message_id`` (modal callbacks where
    ``interaction.message`` is None).

    If the submission is no longer pending, all buttons are disabled.
    """
    # Resolve the review message
    if interaction is not None and interaction.message is not None:
        message = interaction.message
        msg_id = message.id
    elif review_channel_id is not None and review_message_id is not None:
        channel = bot.get_channel(review_channel_id)
        if channel is None:
            channel = await bot.fetch_channel(review_channel_id)
        message = await channel.fetch_message(review_message_id)
        msg_id = review_message_id
    else:
        raise ValueError("Either interaction (with .message) or review_channel_id+review_message_id must be provided")

    with bot.session_scope() as session:
        submission = ApplicationSubmission.get_by_review_message(msg_id, session)
        if submission is None:
            bot.log.warning("application: no submission found for review message %d — was it deleted?", msg_id)
            return
        form = ApplicationForm.get_by_id(submission.FormId, session)
        embed = build_review_embed(submission, form, session)
        status = submission.Status
        applicant_notified = submission.ApplicantNotified

    view = ApplicationReviewView(bot=bot)
    for item in view.children:
        if item.custom_id == "app_review_override":
            item.disabled = status == SubmissionStatus.PENDING
        elif item.custom_id == "app_review_message":
            item.disabled = applicant_notified
        else:
            item.disabled = status != SubmissionStatus.PENDING

    await message.edit(embed=embed, view=view)


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------


def _status_colour(status: SubmissionStatus) -> discord.Colour:
    if status == SubmissionStatus.APPROVED:
        return discord.Colour.green()
    if status == SubmissionStatus.DENIED:
        return discord.Colour.red()
    return discord.Colour.blurple()


async def _dm_applicant(bot, user_id: int, embed: discord.Embed) -> None:
    """Attempt to DM the applicant.  Silently log on Forbidden or NotFound."""
    try:
        user = await bot.fetch_user(user_id)
        await user.send(embed=embed)
    except (discord.Forbidden, discord.NotFound):
        bot.log.warning("Could not DM user %d — DMs are likely disabled or user not found", user_id)


async def _get_or_create_review_thread(bot, review_channel_id: int, review_message_id: int) -> discord.Thread:
    """Return the thread attached to a review embed, creating it (named after the applicant) if absent.

    Raises discord.HTTPException on failure — callers must catch.
    """
    channel = bot.get_channel(review_channel_id)
    if channel is None:
        channel = await bot.fetch_channel(review_channel_id)
    message = await channel.fetch_message(review_message_id)
    if message.thread is not None:
        return message.thread
    with bot.session_scope() as session:
        submission = ApplicationSubmission.get_by_review_message(review_message_id, session)
        thread_name = (submission.UserName if submission else None) or "Application"
    return await message.create_thread(name=thread_name)


async def _post_to_review_thread(
    bot,
    review_channel_id: int,
    review_message_id: int,
    message_text: str,
    reviewer,
    vote_type,
) -> None:
    """Post a reviewer message to the thread attached to the review embed.

    Creates the thread (named after the applicant) if one does not yet exist.
    Raises discord.HTTPException on failure — callers must catch.
    """
    thread = await _get_or_create_review_thread(bot, review_channel_id, review_message_id)
    prefix = "✅" if vote_type == VoteType.APPROVE else "❌"
    await thread.send(f"{prefix} **{reviewer.display_name}**: {message_text}")


def _decision_embed(form_name: str, status: str, custom_message: str | None, reason: str | None) -> discord.Embed:
    """Build the embed sent to the applicant when a decision is made."""
    if status == SubmissionStatus.APPROVED:
        title = "Application Approved"
        colour = discord.Colour.green()
        body = custom_message or f"Your application for **{form_name}** has been approved."
    else:
        title = "Application Denied"
        colour = discord.Colour.red()
        body = custom_message or f"Your application for **{form_name}** has been denied."
        if reason:
            body += f"\n\n**Reason:** {reason}"

    return discord.Embed(title=title, description=body, colour=colour)


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------


class DenyVoteModal(discord.ui.Modal, title="Deny Application"):
    """Modal that collects a required message when denying an application."""

    message = discord.ui.TextInput(
        label="Review note", style=discord.TextStyle.paragraph, required=True, max_length=1000
    )

    def __init__(
        self,
        submission_id: int,
        bot,
        prefill: str | None = None,
        review_channel_id: int = 0,
        review_message_id: int = 0,
    ):
        super().__init__()
        self.submission_id = submission_id
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        if prefill:
            self.message.default = prefill

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        message_text = self.message.value

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status != SubmissionStatus.PENDING:
                await interaction.followup.send("This submission is no longer pending.", ephemeral=True)
                return

            vote = ApplicationVote(SubmissionId=self.submission_id, UserId=interaction.user.id, Vote=VoteType.DENY)
            session.add(vote)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                await interaction.followup.send("You have already voted on this application.", ephemeral=True)
                return

            deny_count = ApplicationVote.count_by_type(self.submission_id, VoteType.DENY, session)
            form = ApplicationForm.get_by_id(submission.FormId, session)

            if deny_count >= form.RequiredDenials:
                submission.Status = SubmissionStatus.DENIED
                submission.DecisionReason = message_text
                session.flush()

        await interaction.followup.send("Your deny vote has been recorded.", ephemeral=True)

        try:
            await _post_to_review_thread(
                self.bot,
                self.review_channel_id,
                self.review_message_id,
                message_text,
                interaction.user,
                VoteType.DENY,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to post deny message to review thread", exc_info=True)

        try:
            await _update_review_embed(
                self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after deny vote", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in DenyVoteModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


class ApproveVoteModal(discord.ui.Modal, title="Approve Application"):
    """Modal that collects a required message when approving an application."""

    message = discord.ui.TextInput(
        label="Review note", style=discord.TextStyle.paragraph, required=True, max_length=1000
    )

    def __init__(
        self,
        submission_id: int,
        bot,
        prefill: str | None = None,
        review_channel_id: int = 0,
        review_message_id: int = 0,
    ):
        super().__init__()
        self.submission_id = submission_id
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        if prefill:
            self.message.default = prefill

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        message_text = self.message.value

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status != SubmissionStatus.PENDING:
                await interaction.followup.send("This submission is no longer pending.", ephemeral=True)
                return

            vote = ApplicationVote(SubmissionId=self.submission_id, UserId=interaction.user.id, Vote=VoteType.APPROVE)
            session.add(vote)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                await interaction.followup.send("You have already voted on this application.", ephemeral=True)
                return

            approve_count = ApplicationVote.count_by_type(self.submission_id, VoteType.APPROVE, session)
            form = ApplicationForm.get_by_id(submission.FormId, session)

            if approve_count >= form.RequiredApprovals:
                submission.Status = SubmissionStatus.APPROVED
                session.flush()

        await interaction.followup.send("Your approval vote has been recorded.", ephemeral=True)

        try:
            await _post_to_review_thread(
                self.bot,
                self.review_channel_id,
                self.review_message_id,
                message_text,
                interaction.user,
                VoteType.APPROVE,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to post approve message to review thread", exc_info=True)

        try:
            await _update_review_embed(
                self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after approve vote", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in ApproveVoteModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


class MessageModal(discord.ui.Modal, title="Message Applicant"):
    """Modal that sends a free-form message to the applicant."""

    message = discord.ui.TextInput(
        label="Message to send", style=discord.TextStyle.paragraph, required=False, max_length=1000
    )

    def __init__(
        self,
        user_id: int,
        bot,
        prefill: str | None = None,
        submission_id: int | None = None,
        review_channel_id: int | None = None,
        review_message_id: int | None = None,
    ):
        super().__init__()
        self.target_user_id = user_id
        self.bot = bot
        self.submission_id = submission_id
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        if prefill:
            self.message.default = prefill

    async def on_submit(self, interaction: discord.Interaction):
        if not self.message.value:
            await interaction.response.send_message("No message sent.", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(self.target_user_id)
            embed = discord.Embed(
                title="Message from a reviewer",
                description=f"**From:** {interaction.user.mention}\n\n{self.message.value}",
                colour=discord.Colour.blurple(),
            )
            await user.send(embed=embed)
            await interaction.response.send_message("Message sent to the applicant.", ephemeral=True)
        except (discord.Forbidden, discord.NotFound):
            await interaction.response.send_message(
                "Could not DM the user — they may have DMs disabled.", ephemeral=True
            )
            return  # DM failed — leave Message button available for retry

        # Mark notified and rebuild the embed only when the submission is decided.
        if self.submission_id is not None:
            with self.bot.session_scope() as session:
                submission = ApplicationSubmission.get_by_id(self.submission_id, session)
                if submission and submission.Status != SubmissionStatus.PENDING:
                    submission.ApplicantNotified = True

            if self.review_channel_id and self.review_message_id:
                try:
                    await _update_review_embed(
                        self.bot,
                        review_channel_id=self.review_channel_id,
                        review_message_id=self.review_message_id,
                    )
                except discord.HTTPException:
                    self.bot.log.error(
                        "application: failed to update review embed after messaging applicant", exc_info=True
                    )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in MessageModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


# ---------------------------------------------------------------------------
# Vote select view (ephemeral, per-session)
# ---------------------------------------------------------------------------


class VoteSelectView(discord.ui.View):
    """Ephemeral view shown after clicking Vote — reviewer picks Approve or Deny from a dropdown.

    Not persistent: it only lives for a single reviewer interaction and does not
    need a fixed ``custom_id`` or ``timeout=None``.
    """

    def __init__(
        self,
        submission_id: int,
        bot,
        review_channel_id: int,
        review_message_id: int,
    ):
        super().__init__(timeout=60)
        self.submission_id = submission_id
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id

    @discord.ui.select(
        placeholder="Select your vote...",
        options=[
            discord.SelectOption(label="Approve", value="approve", emoji="✅"),
            discord.SelectOption(label="Deny", value="deny", emoji="❌"),
        ],
    )
    async def vote_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        vote_type = select.values[0]
        if vote_type == "approve":
            modal = ApproveVoteModal(
                submission_id=self.submission_id,
                bot=self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        else:
            modal = DenyVoteModal(
                submission_id=self.submission_id,
                bot=self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Edit-vote select view and modals (ephemeral, per-session)
# ---------------------------------------------------------------------------


class EditVoteSelectView(discord.ui.View):
    """Ephemeral view for changing an existing vote — pre-selects the reviewer's current vote."""

    def __init__(
        self,
        submission_id: int,
        bot,
        current_vote: VoteType,
        review_channel_id: int,
        review_message_id: int,
    ):
        super().__init__(timeout=60)
        self.submission_id = submission_id
        self.bot = bot
        self.current_vote = current_vote
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        # Override class-level options to mark the current vote as default
        self.vote_select.options = [
            discord.SelectOption(
                label="Approve", value="approve", emoji="✅", default=(current_vote == VoteType.APPROVE)
            ),
            discord.SelectOption(label="Deny", value="deny", emoji="❌", default=(current_vote == VoteType.DENY)),
        ]

    @discord.ui.select(
        placeholder="Change your vote...",
        options=[
            discord.SelectOption(label="Approve", value="approve", emoji="✅"),
            discord.SelectOption(label="Deny", value="deny", emoji="❌"),
        ],
    )
    async def vote_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        vote_type = VoteType.APPROVE if select.values[0] == "approve" else VoteType.DENY
        if vote_type == self.current_vote:
            await interaction.response.send_message(
                "You already cast this vote. Select a different option to change it.", ephemeral=True
            )
            return
        if vote_type == VoteType.APPROVE:
            modal = EditApproveModal(
                submission_id=self.submission_id,
                bot=self.bot,
                previous_vote=self.current_vote,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        else:
            modal = EditDenyModal(
                submission_id=self.submission_id,
                bot=self.bot,
                previous_vote=self.current_vote,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        await interaction.response.send_modal(modal)


class EditApproveModal(discord.ui.Modal, title="Change Vote — Approve"):
    """Modal for changing an existing vote to Approve."""

    message = discord.ui.TextInput(
        label="Review note", style=discord.TextStyle.paragraph, required=True, max_length=1000
    )

    def __init__(
        self,
        submission_id: int,
        bot,
        previous_vote: VoteType,
        review_channel_id: int = 0,
        review_message_id: int = 0,
    ):
        super().__init__()
        self.submission_id = submission_id
        self.bot = bot
        self.previous_vote = previous_vote
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message_text = self.message.value

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status != SubmissionStatus.PENDING:
                await interaction.followup.send("This submission is no longer pending.", ephemeral=True)
                return

            old_vote = ApplicationVote.get_user_vote(self.submission_id, interaction.user.id, session)
            if old_vote:
                session.delete(old_vote)
                session.flush()
            session.add(
                ApplicationVote(SubmissionId=self.submission_id, UserId=interaction.user.id, Vote=VoteType.APPROVE)
            )
            session.flush()

            approve_count = ApplicationVote.count_by_type(self.submission_id, VoteType.APPROVE, session)
            form = ApplicationForm.get_by_id(submission.FormId, session)
            if approve_count >= form.RequiredApprovals:
                submission.Status = SubmissionStatus.APPROVED
                session.flush()

        await interaction.followup.send("Your vote has been changed to Approve.", ephemeral=True)

        prev_emoji = "✅" if self.previous_vote == VoteType.APPROVE else "❌"
        try:
            thread = await _get_or_create_review_thread(self.bot, self.review_channel_id, self.review_message_id)
            await thread.send(f"🔄 **{interaction.user.display_name}** changed vote {prev_emoji}→✅: {message_text}")
        except discord.HTTPException:
            self.bot.log.error("application: failed to post edit-vote message to review thread", exc_info=True)

        try:
            await _update_review_embed(
                self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after edit vote", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in EditApproveModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


class EditDenyModal(discord.ui.Modal, title="Change Vote — Deny"):
    """Modal for changing an existing vote to Deny."""

    message = discord.ui.TextInput(
        label="Review note", style=discord.TextStyle.paragraph, required=True, max_length=1000
    )

    def __init__(
        self,
        submission_id: int,
        bot,
        previous_vote: VoteType,
        review_channel_id: int = 0,
        review_message_id: int = 0,
    ):
        super().__init__()
        self.submission_id = submission_id
        self.bot = bot
        self.previous_vote = previous_vote
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message_text = self.message.value

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status != SubmissionStatus.PENDING:
                await interaction.followup.send("This submission is no longer pending.", ephemeral=True)
                return

            old_vote = ApplicationVote.get_user_vote(self.submission_id, interaction.user.id, session)
            if old_vote:
                session.delete(old_vote)
                session.flush()
            session.add(
                ApplicationVote(SubmissionId=self.submission_id, UserId=interaction.user.id, Vote=VoteType.DENY)
            )
            session.flush()

            deny_count = ApplicationVote.count_by_type(self.submission_id, VoteType.DENY, session)
            form = ApplicationForm.get_by_id(submission.FormId, session)
            if deny_count >= form.RequiredDenials:
                submission.Status = SubmissionStatus.DENIED
                submission.DecisionReason = message_text
                session.flush()

        await interaction.followup.send("Your vote has been changed to Deny.", ephemeral=True)

        prev_emoji = "✅" if self.previous_vote == VoteType.APPROVE else "❌"
        try:
            thread = await _get_or_create_review_thread(self.bot, self.review_channel_id, self.review_message_id)
            await thread.send(f"🔄 **{interaction.user.display_name}** changed vote {prev_emoji}→❌: {message_text}")
        except discord.HTTPException:
            self.bot.log.error("application: failed to post edit-vote message to review thread", exc_info=True)

        try:
            await _update_review_embed(
                self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after edit vote", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in EditDenyModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


class OverrideModal(discord.ui.Modal):
    """Admin/manager modal to flip a decided application APPROVED↔DENIED."""

    reason = discord.ui.TextInput(
        label="Reason for override", style=discord.TextStyle.paragraph, required=True, max_length=1000
    )

    def __init__(
        self,
        current_status: SubmissionStatus,
        submission_id: int,
        bot,
        review_channel_id: int = 0,
        review_message_id: int = 0,
    ):
        new_status = (
            SubmissionStatus.DENIED if current_status == SubmissionStatus.APPROVED else SubmissionStatus.APPROVED
        )
        old_label = current_status.value.capitalize()
        new_label = new_status.value.capitalize()
        super().__init__(title=f"Override: {old_label} → {new_label}")
        self.current_status = current_status
        self.new_status = new_status
        self.submission_id = submission_id
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason_text = self.reason.value

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status == SubmissionStatus.PENDING:
                await interaction.followup.send("Cannot override a pending application.", ephemeral=True)
                return
            submission.Status = self.new_status
            session.flush()

        await interaction.followup.send("Decision overridden.", ephemeral=True)

        old_label = self.current_status.value.capitalize()
        new_label = self.new_status.value.capitalize()
        try:
            thread = await _get_or_create_review_thread(self.bot, self.review_channel_id, self.review_message_id)
            await thread.send(
                f"🔄 **{interaction.user.display_name}** overrode decision: {old_label} → {new_label} — {reason_text}"
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to post override message to review thread", exc_info=True)

        try:
            await _update_review_embed(
                self.bot, review_channel_id=self.review_channel_id, review_message_id=self.review_message_id
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after override", exc_info=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in OverrideModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


# ---------------------------------------------------------------------------
# Persistent review view
# ---------------------------------------------------------------------------


class ApplicationReviewView(discord.ui.View):
    """Four-button persistent view attached to every review embed (Vote, Edit Vote, Message, Override).

    One view instance (registered in ``setup_hook``) handles ALL review embeds
    across all guilds — the submission is looked up via ``interaction.message.id``.
    """

    def __init__(self, bot=None):
        super().__init__(timeout=None)  # persistent — survives bot restarts
        self.bot = bot

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if self.bot:
            self.bot.log.error("Error in ApplicationReviewView: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)

    # -- Vote --------------------------------------------------------------

    @discord.ui.button(label="Vote", style=discord.ButtonStyle.primary, custom_id="app_review_vote")
    async def vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_application_permission(interaction, self.bot):
            await interaction.response.send_message(
                "You do not have permission to review applications.", ephemeral=True
            )
            return

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
            if submission is None:
                await interaction.response.send_message("Submission not found.", ephemeral=True)
                return

            if submission.Status != SubmissionStatus.PENDING:
                await interaction.response.send_message("This application has already been decided.", ephemeral=True)
                return

            existing = ApplicationVote.get_user_vote(submission.Id, interaction.user.id, session)
            if existing:
                await interaction.response.send_message("You have already voted on this application.", ephemeral=True)
                return

            submission_id = submission.Id

        await interaction.response.send_message(
            "Select your vote:",
            view=VoteSelectView(
                submission_id=submission_id,
                bot=self.bot,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
            ),
            ephemeral=True,
        )

    # -- Edit Vote ---------------------------------------------------------

    @discord.ui.button(label="Edit Vote", style=discord.ButtonStyle.secondary, custom_id="app_review_edit_vote")
    async def edit_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_application_permission(interaction, self.bot):
            await interaction.response.send_message(
                "You do not have permission to review applications.", ephemeral=True
            )
            return

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
            if submission is None:
                await interaction.response.send_message("Submission not found.", ephemeral=True)
                return

            if submission.Status != SubmissionStatus.PENDING:
                await interaction.response.send_message("This application has already been decided.", ephemeral=True)
                return

            existing = ApplicationVote.get_user_vote(submission.Id, interaction.user.id, session)
            if existing is None:
                await interaction.response.send_message(
                    "You haven't voted yet. Use the Vote button to cast your vote.", ephemeral=True
                )
                return

            submission_id = submission.Id
            current_vote = existing.Vote

        await interaction.response.send_message(
            "Change your vote:",
            view=EditVoteSelectView(
                submission_id=submission_id,
                bot=self.bot,
                current_vote=current_vote,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
            ),
            ephemeral=True,
        )

    # -- Message -----------------------------------------------------------

    @discord.ui.button(label="Message", style=discord.ButtonStyle.grey, custom_id="app_review_message")
    async def message_applicant(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_application_permission(interaction, self.bot):
            await interaction.response.send_message(
                "You do not have permission to review applications.", ephemeral=True
            )
            return

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
            if submission is None:
                await interaction.response.send_message("Submission not found.", ephemeral=True)
                return

            target_user_id = submission.UserId
            submission_id = submission.Id
            prefill = None
            if submission.Status in (SubmissionStatus.APPROVED, SubmissionStatus.DENIED):
                form = ApplicationForm.get_by_id(submission.FormId, session)
                if form:
                    if submission.Status == SubmissionStatus.APPROVED:
                        prefill = form.ApprovalMessage or f"Your application for **{form.Name}** has been approved."
                    else:
                        prefill = form.DenialMessage or f"Your application for **{form.Name}** has been denied."

        await interaction.response.send_modal(
            MessageModal(
                user_id=target_user_id,
                bot=self.bot,
                prefill=prefill,
                submission_id=submission_id,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
            )
        )

    # -- Override ----------------------------------------------------------

    @discord.ui.button(label="Override", style=discord.ButtonStyle.danger, custom_id="app_review_override")
    async def override(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_override_permission(interaction, self.bot):
            await interaction.response.send_message("You do not have permission to override decisions.", ephemeral=True)
            return

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
            if submission is None:
                await interaction.response.send_message("Submission not found.", ephemeral=True)
                return

            if submission.Status == SubmissionStatus.PENDING:
                await interaction.response.send_message(
                    "This application is still pending — there is no decision to override.", ephemeral=True
                )
                return

            submission_id = submission.Id
            current_status = submission.Status

        await interaction.response.send_modal(
            OverrideModal(
                current_status=current_status,
                submission_id=submission_id,
                bot=self.bot,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
            )
        )
