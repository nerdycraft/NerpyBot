# -*- coding: utf-8 -*-
"""Persistent discord.ui views and modals for the application review system.

ApplicationReviewView — three-button view (Approve / Deny / Message) attached to
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
    """Return True if the user is a guild administrator or holds the application manager role."""
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
    if status != SubmissionStatus.PENDING:
        for item in view.children:
            if item.custom_id == "app_review_message":
                item.disabled = applicant_notified
            else:
                item.disabled = True

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
    channel = bot.get_channel(review_channel_id)
    if channel is None:
        channel = await bot.fetch_channel(review_channel_id)
    message = await channel.fetch_message(review_message_id)

    thread = message.thread
    if thread is None:
        with bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(review_message_id, session)
            thread_name = (submission.UserName if submission else None) or "Application"
        thread = await message.create_thread(name=thread_name)

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


class DenyReasonModal(discord.ui.Modal, title="Deny Application"):
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
        self.bot.log.error("Error in DenyReasonModal: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)


class ApproveMessageModal(discord.ui.Modal, title="Approve Application"):
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
        self.bot.log.error("Error in ApproveMessageModal: %s", error, exc_info=error)
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
        approve_prefill: str,
        deny_prefill: str,
        review_channel_id: int,
        review_message_id: int,
    ):
        super().__init__(timeout=60)
        self.submission_id = submission_id
        self.bot = bot
        self.approve_prefill = approve_prefill
        self.deny_prefill = deny_prefill
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
            modal = ApproveMessageModal(
                submission_id=self.submission_id,
                bot=self.bot,
                prefill=self.approve_prefill,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        else:
            modal = DenyReasonModal(
                submission_id=self.submission_id,
                bot=self.bot,
                prefill=self.deny_prefill,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Persistent review view
# ---------------------------------------------------------------------------


class ApplicationReviewView(discord.ui.View):
    """Two-button persistent view attached to every review embed.

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
                await interaction.response.send_message(
                    "This application has already been decided.", ephemeral=True
                )
                return

            existing = ApplicationVote.get_user_vote(submission.Id, interaction.user.id, session)
            if existing:
                await interaction.response.send_message(
                    "You have already voted on this application.", ephemeral=True
                )
                return

            submission_id = submission.Id

        await interaction.response.send_message(
            "Select your vote:",
            view=VoteSelectView(
                submission_id=submission_id,
                bot=self.bot,
                approve_prefill=None,
                deny_prefill=None,
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
