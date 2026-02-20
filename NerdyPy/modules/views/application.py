# -*- coding: utf-8 -*-
"""Persistent discord.ui views and modals for the application review system.

ApplicationReviewView — three-button view (Approve / Deny / Message) attached to
review embeds in the review channel.  Uses ``timeout=None`` and fixed ``custom_id``
strings so the view survives bot restarts.
"""

import discord

from models.application import ApplicationForm, ApplicationGuildConfig, ApplicationSubmission, ApplicationVote


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------


def check_application_permission(interaction: discord.Interaction, bot) -> bool:
    """Return *True* if the user is an admin or holds the application manager role."""
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
    approve_count = ApplicationVote.count_by_type(submission.Id, "approve", session)
    deny_count = ApplicationVote.count_by_type(submission.Id, "deny", session)

    embed = discord.Embed(title=f"\U0001f4cb {form.Name}", colour=_status_colour(submission.Status))
    embed.add_field(name="Applicant", value=f"<@{submission.UserId}> ({submission.UserName})", inline=True)
    embed.add_field(name="Submitted", value=discord.utils.format_dt(submission.SubmittedAt, style="R"), inline=True)

    for answer in submission.answers:
        # Look up question text — answers are joined-loaded via the submission
        question_text = None
        for q in form.questions:
            if q.Id == answer.QuestionId:
                question_text = q.QuestionText
                break
        label = question_text or f"Question {answer.QuestionId}"
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
            return  # submission was deleted between button click and embed update
        form = ApplicationForm.get_by_id(submission.FormId, session)
        embed = build_review_embed(submission, form, session)

        approve_count = ApplicationVote.count_by_type(submission.Id, "approve", session)
        deny_count = ApplicationVote.count_by_type(submission.Id, "deny", session)
        status = submission.Status
        required_approvals = form.RequiredApprovals
        required_denials = form.RequiredDenials

    view = ApplicationReviewView(
        bot=bot,
        approve_label=f"Approve ({approve_count}/{required_approvals})",
        deny_label=f"Deny ({deny_count}/{required_denials})",
    )
    if status != "pending":
        for item in view.children:
            item.disabled = True

    await message.edit(embed=embed, view=view)


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------


def _status_colour(status: str) -> discord.Colour:
    if status == "approved":
        return discord.Colour.green()
    if status == "denied":
        return discord.Colour.red()
    return discord.Colour.blurple()


async def _dm_applicant(bot, user_id: int, embed: discord.Embed) -> None:
    """Attempt to DM the applicant.  Silently log on Forbidden or NotFound."""
    try:
        user = await bot.fetch_user(user_id)
        await user.send(embed=embed)
    except (discord.Forbidden, discord.NotFound):
        bot.log.warning("Could not DM user %d — DMs are likely disabled or user not found", user_id)


def _decision_embed(form_name: str, status: str, custom_message: str | None, reason: str | None) -> discord.Embed:
    """Build the embed sent to the applicant when a decision is made."""
    if status == "approved":
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
    """Modal that collects an optional reason when denying an application."""

    reason = discord.ui.TextInput(
        label="Reason (optional)", style=discord.TextStyle.paragraph, required=False, max_length=1000
    )

    def __init__(self, submission_id: int, bot, review_channel_id: int = 0, review_message_id: int = 0):
        super().__init__()
        self.submission_id = submission_id
        self.bot = bot
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = self.reason.value or None

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status != "pending":
                await interaction.response.send_message("This submission is no longer pending.", ephemeral=True)
                return

            # Record the deny vote
            vote = ApplicationVote(SubmissionId=self.submission_id, UserId=interaction.user.id, Vote="deny")
            session.add(vote)
            session.flush()

            deny_count = ApplicationVote.count_by_type(self.submission_id, "deny", session)
            form = ApplicationForm.get_by_id(submission.FormId, session)

            if deny_count >= form.RequiredDenials:
                submission.Status = "denied"
                submission.DecisionReason = reason_text
                session.flush()

                # DM applicant
                embed = _decision_embed(form.Name, "denied", form.DenialMessage, reason_text)
                await _dm_applicant(self.bot, submission.UserId, embed)

        # Respond to the modal interaction first (modal submits have no .message)
        await interaction.response.send_message("Your deny vote has been recorded.", ephemeral=True)

        # Update the review embed using stored channel/message IDs
        await _update_review_embed(
            self.bot,
            review_channel_id=self.review_channel_id,
            review_message_id=self.review_message_id,
        )


class MessageModal(discord.ui.Modal, title="Message Applicant"):
    """Modal that sends a free-form message to the applicant."""

    message = discord.ui.TextInput(
        label="Message to send", style=discord.TextStyle.paragraph, required=True, max_length=1000
    )

    def __init__(self, user_id: int, bot):
        super().__init__()
        self.target_user_id = user_id
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
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


# ---------------------------------------------------------------------------
# Persistent review view
# ---------------------------------------------------------------------------


class ApplicationReviewView(discord.ui.View):
    """Three-button persistent view attached to every review embed.

    One view instance (registered in ``setup_hook``) handles ALL review embeds
    across all guilds — the submission is looked up via ``interaction.message.id``.

    For the persistent registration at startup, labels default to plain
    "Approve" / "Deny".  When rebuilding the view in ``_update_review_embed``,
    dynamic labels with vote counts are passed (e.g. "Approve (1/2)").
    """

    def __init__(self, bot=None, approve_label: str = "Approve", deny_label: str = "Deny"):
        super().__init__(timeout=None)  # persistent — survives bot restarts
        self.bot = bot
        # Update button labels if custom ones were provided
        self.approve.label = approve_label
        self.deny.label = deny_label

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if self.bot:
            self.bot.log.error("Error in ApplicationReviewView: %s", error, exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("An error occurred. Please try again later.", ephemeral=True)
        else:
            await interaction.followup.send("An error occurred. Please try again later.", ephemeral=True)

    # -- Approve -----------------------------------------------------------

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="app_review_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
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

            if submission.Status != "pending":
                await interaction.response.send_message("This application has already been decided.", ephemeral=True)
                return

            existing = ApplicationVote.get_user_vote(submission.Id, interaction.user.id, session)
            if existing:
                await interaction.response.send_message("You have already voted on this application.", ephemeral=True)
                return

            vote = ApplicationVote(SubmissionId=submission.Id, UserId=interaction.user.id, Vote="approve")
            session.add(vote)
            session.flush()

            approve_count = ApplicationVote.count_by_type(submission.Id, "approve", session)
            form = ApplicationForm.get_by_id(submission.FormId, session)

            if approve_count >= form.RequiredApprovals:
                submission.Status = "approved"
                session.flush()

                embed = _decision_embed(form.Name, "approved", form.ApprovalMessage, None)
                await _dm_applicant(self.bot, submission.UserId, embed)

        # Respond first to acknowledge within Discord's 3-second window,
        # then update the review embed (message.edit uses the bot HTTP client, not the interaction).
        await interaction.response.send_message("Your approval vote has been recorded.", ephemeral=True)
        await _update_review_embed(self.bot, interaction=interaction)

    # -- Deny --------------------------------------------------------------

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="app_review_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
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

            if submission.Status != "pending":
                await interaction.response.send_message("This application has already been decided.", ephemeral=True)
                return

            existing = ApplicationVote.get_user_vote(submission.Id, interaction.user.id, session)
            if existing:
                await interaction.response.send_message("You have already voted on this application.", ephemeral=True)
                return

            submission_id = submission.Id

        # Open the deny-reason modal — pass review message coordinates so the
        # modal callback can edit the review embed (modal submits lack .message).
        await interaction.response.send_modal(
            DenyReasonModal(
                submission_id=submission_id,
                bot=self.bot,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
            )
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

        await interaction.response.send_modal(MessageModal(user_id=target_user_id, bot=self.bot))
