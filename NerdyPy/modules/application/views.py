# -*- coding: utf-8 -*-
"""Persistent discord.ui views and modals for the application review system.

ApplicationReviewView — six-button persistent view (◀ / ▶ / Vote / Edit Vote / Message / Override)
attached to review embeds in the review channel.  Uses ``timeout=None`` and fixed ``custom_id``
strings so the view survives bot restarts.  ◀/▶ are hidden when the form has ≤23 answers.

ApplicationApplyView — single-button persistent view ("Apply") posted in a public channel.
Clicking it starts the same DM conversation as ``/apply``.
"""

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

import discord
from cachetools import LRUCache
from sqlalchemy.exc import IntegrityError

from models.application import (
    ApplicationForm,
    ApplicationGuildRole,
    ApplicationSubmission,
    ApplicationVote,
    SubmissionStatus,
    VoteType,
)
from utils.helpers import bot_get_or_fetch_channel, send_hidden_message
from utils.strings import get_string

# Discord enforces a hard 25-field limit per embed.  Two fields are fixed (applicant +
# submitted_at), leaving 23 slots for answers.
_ANSWERS_PER_PAGE = 23

# Runtime cache: maps review message_id → (current_page, total_pages), both 1-based.
# Populated on first ◀/▶ click; cleared on bot restart (harmless — full state is
# recovered from the embed footer regex on the next click).  Bounded to 1 000 entries
# so long-running bots don't accumulate stale entries indefinitely.
_review_page_cache: LRUCache = LRUCache(maxsize=1000)

# Regex used to recover pagination state from an embed footer after a bot restart.
# Locale-agnostic: matches the numeric X/Y part regardless of surrounding text.
_PAGE_RE = re.compile(r"(\d+)/(\d+)")


def _parse_page_from_footer(footer: str) -> tuple[int, int] | None:
    # The footer contains multiple X/Y patterns (approvals, denials, then page).
    # Page info is always last — take the final match.
    matches = _PAGE_RE.findall(footer)
    return (int(matches[-1][0]), int(matches[-1][1])) if matches else None


# Button custom_id constants — shared by decorators, __init__ label lookup, and update_review_embed.
_BTN_VOTE = "app_review_vote"
_BTN_EDIT_VOTE = "app_review_edit_vote"
_BTN_MESSAGE = "app_review_message"
_BTN_OVERRIDE = "app_review_override"
_BTN_PREV = "app_review_prev"
_BTN_NEXT = "app_review_next"
_BTN_APPLY = "app_apply_button"


def _normalize_review_view(
    view: "ApplicationReviewView",
    *,
    total_pages: int,
    current_page: int,
    status: "SubmissionStatus",
    applicant_notified: bool,
) -> None:
    """Mutate *view* in-place: remove/disable buttons based on pagination and submission state.

    Called on both the initial embed send and every subsequent re-render so that first
    render and re-render are always in sync.
    """
    for item in list(view.children):
        cid = item.custom_id
        if total_pages <= 1 and cid in (_BTN_PREV, _BTN_NEXT):
            view.remove_item(item)
        elif cid == _BTN_OVERRIDE:
            item.disabled = status == SubmissionStatus.PENDING
        elif cid == _BTN_MESSAGE:
            item.disabled = applicant_notified
        elif cid == _BTN_PREV:
            item.disabled = current_page <= 1
        elif cid == _BTN_NEXT:
            item.disabled = current_page >= total_pages
        else:
            item.disabled = status != SubmissionStatus.PENDING


# ---------------------------------------------------------------------------
# Pre-loaded data carriers (used by bulk language-refresh to avoid N+1 sessions)
# ---------------------------------------------------------------------------


@dataclass
class ApplyEmbedData:
    """Scalar data needed to edit an Apply button embed without a DB session."""

    channel_id: int
    message_id: int
    form_name: str
    description: str | None
    lang: str


@dataclass
class ReviewEmbedData:
    """Scalar data needed to rebuild a review embed without a DB session."""

    user_id: int
    user_name: str
    submitted_at: datetime
    status: SubmissionStatus
    applicant_notified: bool
    form_name: str
    required_approvals: int
    required_denials: int
    lang: str
    approve_count: int
    deny_count: int
    answers: list[tuple[str, str | None]]
    page: int = field(default=1)
    total_pages: int = field(default=1)


@dataclass
class RoutedReviewEmbed:
    """Pairs pre-extracted review embed data with its Discord message location."""

    data: "ReviewEmbedData"
    channel_id: int
    message_id: int


def extract_answers(answers) -> list[tuple[str, str | None]]:
    """Extract (question_text, answer_text) pairs from an answer collection."""
    return [(a.question.QuestionText if a.question else f"Question {a.QuestionId}", a.AnswerText) for a in answers]


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------


def check_application_permission(interaction: discord.Interaction, bot) -> bool:
    """Return True if the user is a guild administrator, holds a manager role, or holds a reviewer role."""
    if interaction.user.guild_permissions.administrator:
        return True
    user_role_ids = {r.id for r in interaction.user.roles}
    with bot.session_scope() as session:
        manager_ids = ApplicationGuildRole.get_role_ids(interaction.guild.id, "manager", session)
        if any(rid in user_role_ids for rid in manager_ids):
            return True
        reviewer_ids = ApplicationGuildRole.get_role_ids(interaction.guild.id, "reviewer", session)
        return any(rid in user_role_ids for rid in reviewer_ids)


def check_override_permission(interaction: discord.Interaction, bot) -> bool:
    """Return True if the user is a guild administrator or holds a manager role.

    Reviewer role holders are NOT allowed to override decisions.
    """
    if interaction.user.guild_permissions.administrator:
        return True
    user_role_ids = {r.id for r in interaction.user.roles}
    with bot.session_scope() as session:
        manager_ids = ApplicationGuildRole.get_role_ids(interaction.guild.id, "manager", session)
        return any(rid in user_role_ids for rid in manager_ids)


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


def build_review_embed(
    submission,
    form,
    session,
    lang: str = "en",
    page: int = 1,
    *,
    answers: "list[tuple[str, str | None]] | None" = None,
) -> discord.Embed:
    """Build the review embed shown in the review channel for a submission.

    Pass pre-extracted *answers* to skip the internal ``extract_answers`` call
    when the caller already has the list (avoids a second traversal).
    """
    all_answers = answers if answers is not None else extract_answers(submission.answers)
    total_pages = max(1, math.ceil(len(all_answers) / _ANSWERS_PER_PAGE))
    page = max(1, min(page, total_pages))
    return _build_review_embed_from_data(
        ReviewEmbedData(
            user_id=submission.UserId,
            user_name=submission.UserName,
            submitted_at=submission.SubmittedAt,
            status=submission.Status,
            applicant_notified=submission.ApplicantNotified,
            form_name=form.Name,
            required_approvals=form.RequiredApprovals,
            required_denials=form.RequiredDenials,
            lang=lang,
            approve_count=sum(1 for v in submission.votes if v.Vote == VoteType.APPROVE),
            deny_count=sum(1 for v in submission.votes if v.Vote == VoteType.DENY),
            answers=all_answers,
            page=page,
            total_pages=total_pages,
        )
    )


def _build_review_embed_from_data(data: "ReviewEmbedData") -> discord.Embed:
    """Build the review embed from pre-extracted scalar data (no DB session needed).

    Renders only the answers for the current page (up to ``_ANSWERS_PER_PAGE`` per page).
    Answer values that exceed Discord's 1024-character field limit are truncated with ``…``.
    When the form spans multiple pages, the footer includes the current page indicator.
    """
    embed = discord.Embed(title=f"\U0001f4cb {data.form_name}", colour=_status_colour(data.status))
    embed.add_field(
        name=get_string(data.lang, "application.review.applicant"),
        value=f"<@{data.user_id}> ({data.user_name})",
        inline=True,
    )
    submitted_at = data.submitted_at
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=UTC)
    embed.add_field(
        name=get_string(data.lang, "application.review.submitted"),
        value=discord.utils.format_dt(submitted_at, style="R"),
        inline=True,
    )

    offset = (data.page - 1) * _ANSWERS_PER_PAGE
    page_answers = data.answers[offset : offset + _ANSWERS_PER_PAGE]
    no_answer = get_string(data.lang, "application.review.no_answer")
    for label, answer_text in page_answers:
        if len(label) > 256:
            label = label[:255] + "…"
        value = answer_text or no_answer
        if len(value) > 1024:
            value = value[:1023] + "…"
        embed.add_field(name=label, value=value, inline=False)

    footer_text = get_string(
        data.lang,
        "application.review.footer",
        status=data.status.capitalize(),
        approvals=data.approve_count,
        required_approvals=data.required_approvals,
        denials=data.deny_count,
        required_denials=data.required_denials,
    )
    if data.total_pages > 1:
        page_info = get_string(data.lang, "application.review.page_info", page=data.page, total=data.total_pages)
        footer_text = f"{footer_text}  |  {page_info}"
    embed.set_footer(text=footer_text)
    return embed


async def update_review_embed(
    bot,
    *,
    interaction: discord.Interaction | None = None,
    review_channel_id: int | None = None,
    review_message_id: int | None = None,
    preloaded: "ReviewEmbedData | None" = None,
    page: int | None = None,
):
    """Rebuild and edit the review embed with current vote counts.

    Can be called either with an ``interaction`` (button callbacks where
    ``interaction.message`` is the review embed) or with explicit
    ``review_channel_id`` / ``review_message_id`` (modal callbacks where
    ``interaction.message`` is None).

    If the submission is no longer pending, all buttons are disabled.

    Pass ``preloaded`` to skip the database lookup entirely (used by bulk language-refresh).
    Pass ``page`` to show a specific page of answers; defaults to 1.
    """
    # Resolve the review message
    if interaction is not None and interaction.message is not None:
        message = interaction.message
        msg_id = message.id
    elif review_channel_id is not None and review_message_id is not None:
        channel = await bot_get_or_fetch_channel(bot, review_channel_id)
        if channel is None:
            return
        message = await channel.fetch_message(review_message_id)
        msg_id = review_message_id
    else:
        raise ValueError("Either interaction (with .message) or review_channel_id+review_message_id must be provided")

    if page is not None:
        current_page = page
    elif msg_id in _review_page_cache:
        current_page = _review_page_cache[msg_id][0]
    else:
        embed = message.embeds[0] if message.embeds else None
        footer_raw = embed.footer.text if embed and embed.footer else None
        current_page = (_parse_page_from_footer(footer_raw if isinstance(footer_raw, str) else "") or (1, 1))[0]

    if preloaded is not None:
        preloaded.total_pages = max(1, math.ceil(len(preloaded.answers) / _ANSWERS_PER_PAGE))
        preloaded.page = max(1, min(current_page, preloaded.total_pages))
        embed = _build_review_embed_from_data(preloaded)
        status = preloaded.status
        applicant_notified = preloaded.applicant_notified
        lang = preloaded.lang
        total_pages = preloaded.total_pages
    else:
        with bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(msg_id, session)
            if submission is None:
                bot.log.warning("application: no submission found for review message %d — was it deleted?", msg_id)
                return
            form = ApplicationForm.get_by_id(submission.FormId, session)
            lang = bot.get_guild_language(submission.GuildId)
            all_answers = extract_answers(submission.answers)
            total_pages = max(1, math.ceil(len(all_answers) / _ANSWERS_PER_PAGE))
            current_page = max(1, min(current_page, total_pages))
            embed = build_review_embed(submission, form, session, lang, page=current_page, answers=all_answers)
            status = submission.Status
            applicant_notified = submission.ApplicantNotified

    view = ApplicationReviewView(bot=bot, lang=lang)
    _normalize_review_view(
        view,
        total_pages=total_pages,
        current_page=current_page,
        status=status,
        applicant_notified=applicant_notified,
    )
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
    channel = await bot_get_or_fetch_channel(bot, review_channel_id)
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


def _decision_embed(
    form_name: str, status: str, custom_message: str | None, reason: str | None, lang: str = "en"
) -> discord.Embed:
    """Build the embed sent to the applicant when a decision is made."""
    if status == SubmissionStatus.APPROVED:
        title = get_string(lang, "application.decision.approved_title")
        colour = discord.Colour.green()
        body = custom_message or get_string(lang, "application.decision.approved_default", form=form_name)
    else:
        title = get_string(lang, "application.decision.denied_title")
        colour = discord.Colour.red()
        body = custom_message or get_string(lang, "application.decision.denied_default", form=form_name)
        if reason:
            body += "\n\n" + get_string(lang, "application.decision.reason", reason=reason)

    return discord.Embed(title=title, description=body, colour=colour)


# ---------------------------------------------------------------------------
# Shared vote helpers
# ---------------------------------------------------------------------------


def _check_vote_threshold(session, submission, vote_type, message_text):
    """Check if the vote threshold is met and update submission status accordingly."""
    count = ApplicationVote.count_by_type(submission.Id, vote_type, session)
    form = ApplicationForm.get_by_id(submission.FormId, session)
    if vote_type == VoteType.APPROVE and count >= form.RequiredApprovals:
        submission.Status = SubmissionStatus.APPROVED
        session.flush()
    elif vote_type == VoteType.DENY and count >= form.RequiredDenials:
        submission.Status = SubmissionStatus.DENIED
        submission.DecisionReason = message_text
        session.flush()


async def _record_first_vote(session, interaction, submission_id, vote_type, message_text, lang):
    """Record a first-time vote; returns True on success, False (with followup error) on failure."""
    submission = ApplicationSubmission.get_by_id(submission_id, session)
    if submission is None or submission.Status != SubmissionStatus.PENDING:
        await interaction.followup.send(get_string(lang, "application.review.no_longer_pending"), ephemeral=True)
        return False

    vote = ApplicationVote(
        SubmissionId=submission_id, UserId=interaction.user.id, VoterName=interaction.user.display_name, Vote=vote_type
    )
    session.add(vote)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        await interaction.followup.send(get_string(lang, "application.review.already_voted"), ephemeral=True)
        return False

    _check_vote_threshold(session, submission, vote_type, message_text)
    return True


async def _record_edit_vote(session, interaction, submission_id, vote_type, message_text, lang):
    """Replace an existing vote; returns True on success, False (with followup error) on failure."""
    submission = ApplicationSubmission.get_by_id(submission_id, session)
    if submission is None or submission.Status != SubmissionStatus.PENDING:
        await interaction.followup.send(get_string(lang, "application.review.no_longer_pending"), ephemeral=True)
        return False

    old_vote = ApplicationVote.get_user_vote(submission_id, interaction.user.id, session)
    if old_vote:
        session.delete(old_vote)
        session.flush()
    session.add(
        ApplicationVote(
            SubmissionId=submission_id,
            UserId=interaction.user.id,
            VoterName=interaction.user.display_name,
            Vote=vote_type,
        )
    )
    session.flush()

    _check_vote_threshold(session, submission, vote_type, message_text)
    return True


async def _post_edit_and_update_embed(
    bot, review_channel_id, review_message_id, user, previous_vote, new_emoji, message_text
):
    """Post an edit-vote message to the review thread and update the review embed."""
    prev_emoji = "✅" if previous_vote == VoteType.APPROVE else "❌"
    try:
        thread = await _get_or_create_review_thread(bot, review_channel_id, review_message_id)
        await thread.send(f"🔄 **{user.display_name}** changed vote {prev_emoji}→{new_emoji}: {message_text}")
    except discord.HTTPException:
        bot.log.error("application: failed to post edit-vote message to review thread", exc_info=True)

    try:
        await update_review_embed(bot, review_channel_id=review_channel_id, review_message_id=review_message_id)
    except discord.HTTPException:
        bot.log.error("application: failed to update review embed after edit vote", exc_info=True)


async def _validate_review_interaction(bot, interaction, session):
    """Check permission, look up submission, verify pending. Returns (lang, submission, existing_vote) or None."""
    lang = bot.get_guild_language(interaction.guild_id)
    if not check_application_permission(interaction, bot):
        await interaction.response.send_message(
            get_string(lang, "application.review.no_review_permission"), ephemeral=True
        )
        return None

    submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
    if submission is None:
        await interaction.response.send_message(get_string(lang, "application.review.not_found"), ephemeral=True)
        return None

    if submission.Status != SubmissionStatus.PENDING:
        await interaction.response.send_message(get_string(lang, "application.review.already_decided"), ephemeral=True)
        return None

    existing = ApplicationVote.get_user_vote(submission.Id, interaction.user.id, session)
    return lang, submission, existing


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------


class _ApplicationModal(discord.ui.Modal):
    """Base class for application modals providing shared on_error handling."""

    bot: object
    lang: str

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        self.bot.log.error("Error in %s: %s", self.__class__.__name__, error, exc_info=error)
        await send_hidden_message(interaction, get_string(self.lang, "application.error_generic"))


class DenyVoteModal(_ApplicationModal):
    """Modal that collects a required message when denying an application."""

    def __init__(
        self,
        submission_id: int,
        bot,
        prefill: str | None = None,
        review_channel_id: int = 0,
        review_message_id: int = 0,
        lang: str = "en",
    ):
        super().__init__(title=get_string(lang, "application.modal.deny_title"))
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self._message = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=True, max_length=1000)
        if prefill:
            self._message.default = prefill
        self.add_item(
            discord.ui.Label(text=get_string(lang, "application.modal.review_note_label"), component=self._message)
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message_text = self._message.value

        with self.bot.session_scope() as session:
            if not await _record_first_vote(
                session, interaction, self.submission_id, VoteType.DENY, message_text, self.lang
            ):
                return

        await interaction.followup.send(get_string(self.lang, "application.review.deny_recorded"), ephemeral=True)

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
            await update_review_embed(
                self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after deny vote", exc_info=True)


class ApproveVoteModal(_ApplicationModal):
    """Modal that collects a required message when approving an application."""

    def __init__(
        self,
        submission_id: int,
        bot,
        prefill: str | None = None,
        review_channel_id: int = 0,
        review_message_id: int = 0,
        lang: str = "en",
    ):
        super().__init__(title=get_string(lang, "application.modal.approve_title"))
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self._message = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=True, max_length=1000)
        if prefill:
            self._message.default = prefill
        self.add_item(
            discord.ui.Label(text=get_string(lang, "application.modal.review_note_label"), component=self._message)
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message_text = self._message.value

        with self.bot.session_scope() as session:
            if not await _record_first_vote(
                session, interaction, self.submission_id, VoteType.APPROVE, message_text, self.lang
            ):
                return

        await interaction.followup.send(get_string(self.lang, "application.review.approve_recorded"), ephemeral=True)

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
            await update_review_embed(
                self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after approve vote", exc_info=True)


class MessageModal(_ApplicationModal):
    """Modal that sends a free-form message to the applicant."""

    def __init__(
        self,
        user_id: int,
        bot,
        prefill: str | None = None,
        submission_id: int | None = None,
        review_channel_id: int | None = None,
        review_message_id: int | None = None,
        lang: str = "en",
    ):
        super().__init__(title=get_string(lang, "application.message_modal.title"))
        self.target_user_id = user_id
        self.bot = bot
        self.lang = lang
        self.submission_id = submission_id
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self._message = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=False, max_length=1000)
        if prefill:
            self._message.default = prefill
        self.add_item(
            discord.ui.Label(text=get_string(lang, "application.modal.message_label"), component=self._message)
        )

    async def on_submit(self, interaction: discord.Interaction):
        if not self._message.value:
            await interaction.response.send_message(
                get_string(self.lang, "application.message_modal.no_content"), ephemeral=True
            )
            return

        try:
            user = await self.bot.fetch_user(self.target_user_id)
            embed = discord.Embed(
                title=get_string(self.lang, "application.message_modal.reviewer_title"),
                description=f"**From:** {interaction.user.mention}\n\n{self._message.value}",
                colour=discord.Colour.blurple(),
            )
            await user.send(embed=embed)
            await interaction.response.send_message(
                get_string(self.lang, "application.message_modal.sent"), ephemeral=True
            )
        except (discord.Forbidden, discord.NotFound):
            await interaction.response.send_message(
                get_string(self.lang, "application.message_modal.dm_failed"), ephemeral=True
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
                    await update_review_embed(
                        self.bot,
                        review_channel_id=self.review_channel_id,
                        review_message_id=self.review_message_id,
                    )
                except discord.HTTPException:
                    self.bot.log.error(
                        "application: failed to update review embed after messaging applicant", exc_info=True
                    )


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
        lang: str = "en",
    ):
        super().__init__(timeout=60)
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self.vote_select.placeholder = get_string(lang, "application.review.vote_select_placeholder")
        self.vote_select.options = [
            discord.SelectOption(
                label=get_string(lang, "application.review.approve_label"), value="approve", emoji="✅"
            ),
            discord.SelectOption(label=get_string(lang, "application.review.deny_label"), value="deny", emoji="❌"),
        ]

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
                lang=self.lang,
            )
        else:
            modal = DenyVoteModal(
                submission_id=self.submission_id,
                bot=self.bot,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
                lang=self.lang,
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
        lang: str = "en",
    ):
        super().__init__(timeout=60)
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.current_vote = current_vote
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        # Override class-level placeholder and options; mark the current vote as default
        self.vote_select.placeholder = get_string(lang, "application.review.vote_change_placeholder")
        self.vote_select.options = [
            discord.SelectOption(
                label=get_string(lang, "application.review.approve_label"),
                value="approve",
                emoji="✅",
                default=(current_vote == VoteType.APPROVE),
            ),
            discord.SelectOption(
                label=get_string(lang, "application.review.deny_label"),
                value="deny",
                emoji="❌",
                default=(current_vote == VoteType.DENY),
            ),
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
                get_string(self.lang, "application.review.same_vote"), ephemeral=True
            )
            return
        if vote_type == VoteType.APPROVE:
            modal = EditApproveModal(
                submission_id=self.submission_id,
                bot=self.bot,
                previous_vote=self.current_vote,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
                lang=self.lang,
            )
        else:
            modal = EditDenyModal(
                submission_id=self.submission_id,
                bot=self.bot,
                previous_vote=self.current_vote,
                review_channel_id=self.review_channel_id,
                review_message_id=self.review_message_id,
                lang=self.lang,
            )
        await interaction.response.send_modal(modal)


class EditApproveModal(_ApplicationModal):
    """Modal for changing an existing vote to Approve."""

    def __init__(
        self,
        submission_id: int,
        bot,
        previous_vote: VoteType,
        review_channel_id: int = 0,
        review_message_id: int = 0,
        lang: str = "en",
    ):
        super().__init__(title=get_string(lang, "application.modal.edit_approve_title"))
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.previous_vote = previous_vote
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self._message = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(
            discord.ui.Label(text=get_string(lang, "application.modal.review_note_label"), component=self._message)
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message_text = self._message.value

        with self.bot.session_scope() as session:
            if not await _record_edit_vote(
                session, interaction, self.submission_id, VoteType.APPROVE, message_text, self.lang
            ):
                return

        await interaction.followup.send(
            get_string(self.lang, "application.review.vote_changed_approve"), ephemeral=True
        )
        await _post_edit_and_update_embed(
            self.bot,
            self.review_channel_id,
            self.review_message_id,
            interaction.user,
            self.previous_vote,
            "✅",
            message_text,
        )


class EditDenyModal(_ApplicationModal):
    """Modal for changing an existing vote to Deny."""

    def __init__(
        self,
        submission_id: int,
        bot,
        previous_vote: VoteType,
        review_channel_id: int = 0,
        review_message_id: int = 0,
        lang: str = "en",
    ):
        super().__init__(title=get_string(lang, "application.modal.edit_deny_title"))
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.previous_vote = previous_vote
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self._message = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(
            discord.ui.Label(text=get_string(lang, "application.modal.review_note_label"), component=self._message)
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        message_text = self._message.value

        with self.bot.session_scope() as session:
            if not await _record_edit_vote(
                session, interaction, self.submission_id, VoteType.DENY, message_text, self.lang
            ):
                return

        await interaction.followup.send(get_string(self.lang, "application.review.vote_changed_deny"), ephemeral=True)
        await _post_edit_and_update_embed(
            self.bot,
            self.review_channel_id,
            self.review_message_id,
            interaction.user,
            self.previous_vote,
            "❌",
            message_text,
        )


class OverrideModal(_ApplicationModal):
    """Admin/manager modal to flip a decided application APPROVED↔DENIED."""

    def __init__(
        self,
        current_status: SubmissionStatus,
        submission_id: int,
        bot,
        review_channel_id: int = 0,
        review_message_id: int = 0,
        lang: str = "en",
    ):
        new_status = (
            SubmissionStatus.DENIED if current_status == SubmissionStatus.APPROVED else SubmissionStatus.APPROVED
        )
        old_label = current_status.value.capitalize()
        new_label = new_status.value.capitalize()
        super().__init__(title=get_string(lang, "application.modal.override_title", old=old_label, new=new_label))
        self.current_status = current_status
        self.new_status = new_status
        self.submission_id = submission_id
        self.bot = bot
        self.lang = lang
        self.review_channel_id = review_channel_id
        self.review_message_id = review_message_id
        self._reason = discord.ui.TextInput(style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(
            discord.ui.Label(text=get_string(lang, "application.modal.override_reason_label"), component=self._reason)
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        reason_text = self._reason.value

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_id(self.submission_id, session)
            if submission is None or submission.Status == SubmissionStatus.PENDING:
                await interaction.followup.send(
                    get_string(self.lang, "application.review.override_cannot_pending"), ephemeral=True
                )
                return
            submission.Status = self.new_status
            session.flush()

        await interaction.followup.send(get_string(self.lang, "application.review.override_success"), ephemeral=True)

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
            await update_review_embed(
                self.bot, review_channel_id=self.review_channel_id, review_message_id=self.review_message_id
            )
        except discord.HTTPException:
            self.bot.log.error("application: failed to update review embed after override", exc_info=True)


# ---------------------------------------------------------------------------
# Persistent review view
# ---------------------------------------------------------------------------


class ApplicationReviewView(discord.ui.View):
    """Six-button persistent view attached to every review embed (◀ / ▶ / Vote / Edit Vote / Message / Override).

    One view instance (registered in ``setup_hook``) handles ALL review embeds
    across all guilds — the submission is looked up via ``interaction.message.id``.

    ◀/▶ (row 1) are hidden when the form has ≤23 answers and disabled at page
    boundaries.  ``update_review_embed`` handles both via ``remove_item`` /
    per-item ``disabled`` assignment on each fresh view instance.
    """

    def __init__(self, bot=None, lang: str = "en"):
        super().__init__(timeout=None)  # persistent — survives bot restarts
        self.bot = bot
        # _BTN_PREV and _BTN_NEXT use emoji (◀/▶) and need no label localization.
        for item in self.children:
            if item.custom_id == _BTN_VOTE:
                item.label = get_string(lang, "application.review.btn_vote")
            elif item.custom_id == _BTN_EDIT_VOTE:
                item.label = get_string(lang, "application.review.btn_edit_vote")
            elif item.custom_id == _BTN_MESSAGE:
                item.label = get_string(lang, "application.review.btn_message")
            elif item.custom_id == _BTN_OVERRIDE:
                item.label = get_string(lang, "application.review.btn_override")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if self.bot:
            self.bot.log.error("Error in ApplicationReviewView: %s", error, exc_info=error)
            lang = self.bot.get_guild_language(interaction.guild_id)
        else:
            lang = "en"
        await send_hidden_message(interaction, get_string(lang, "application.error_generic"))

    # -- Vote --------------------------------------------------------------

    @discord.ui.button(label="Vote", style=discord.ButtonStyle.primary, custom_id=_BTN_VOTE)
    async def vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        with self.bot.session_scope() as session:
            result = await _validate_review_interaction(self.bot, interaction, session)
            if result is None:
                return
            lang, submission, existing = result

            if existing:
                await interaction.response.send_message(
                    get_string(lang, "application.review.already_voted"), ephemeral=True
                )
                return

            submission_id = submission.Id

        await interaction.response.send_message(
            get_string(lang, "application.review.select_vote"),
            view=VoteSelectView(
                submission_id=submission_id,
                bot=self.bot,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
                lang=lang,
            ),
            ephemeral=True,
        )

    # -- Edit Vote ---------------------------------------------------------

    @discord.ui.button(label="Edit Vote", style=discord.ButtonStyle.secondary, custom_id=_BTN_EDIT_VOTE)
    async def edit_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        with self.bot.session_scope() as session:
            result = await _validate_review_interaction(self.bot, interaction, session)
            if result is None:
                return
            lang, submission, existing = result

            if existing is None:
                await interaction.response.send_message(
                    get_string(lang, "application.review.no_vote_yet"), ephemeral=True
                )
                return

            submission_id = submission.Id
            current_vote = existing.Vote

        await interaction.response.send_message(
            get_string(lang, "application.review.change_vote"),
            view=EditVoteSelectView(
                submission_id=submission_id,
                bot=self.bot,
                current_vote=current_vote,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
                lang=lang,
            ),
            ephemeral=True,
        )

    # -- Message -----------------------------------------------------------

    @discord.ui.button(label="Message", style=discord.ButtonStyle.grey, custom_id=_BTN_MESSAGE)
    async def message_applicant(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.bot.get_guild_language(interaction.guild_id)
        if not check_application_permission(interaction, self.bot):
            await interaction.response.send_message(
                get_string(lang, "application.review.no_review_permission"), ephemeral=True
            )
            return

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
            if submission is None:
                await interaction.response.send_message(
                    get_string(lang, "application.review.not_found"), ephemeral=True
                )
                return

            target_user_id = submission.UserId
            submission_id = submission.Id
            prefill = None
            if submission.Status in (SubmissionStatus.APPROVED, SubmissionStatus.DENIED):
                form = ApplicationForm.get_by_id(submission.FormId, session)
                if form:
                    if submission.Status == SubmissionStatus.APPROVED:
                        prefill = form.ApprovalMessage or get_string(
                            lang, "application.decision.approved_default", form=form.Name
                        )
                    else:
                        prefill = form.DenialMessage or get_string(
                            lang, "application.decision.denied_default", form=form.Name
                        )

        await interaction.response.send_modal(
            MessageModal(
                user_id=target_user_id,
                bot=self.bot,
                prefill=prefill,
                submission_id=submission_id,
                review_channel_id=interaction.message.channel.id,
                review_message_id=interaction.message.id,
                lang=lang,
            )
        )

    # -- Override ----------------------------------------------------------

    @discord.ui.button(label="Override", style=discord.ButtonStyle.danger, custom_id=_BTN_OVERRIDE)
    async def override(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self.bot.get_guild_language(interaction.guild_id)
        if not check_override_permission(interaction, self.bot):
            await interaction.response.send_message(
                get_string(lang, "application.review.no_override_permission"), ephemeral=True
            )
            return

        with self.bot.session_scope() as session:
            submission = ApplicationSubmission.get_by_review_message(interaction.message.id, session)
            if submission is None:
                await interaction.response.send_message(
                    get_string(lang, "application.review.not_found"), ephemeral=True
                )
                return

            if submission.Status == SubmissionStatus.PENDING:
                await interaction.response.send_message(
                    get_string(lang, "application.review.override_pending"), ephemeral=True
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
                lang=lang,
            )
        )

    # -- Pagination --------------------------------------------------------

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary, custom_id=_BTN_PREV, row=1)
    async def page_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._navigate(interaction, delta=-1)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary, custom_id=_BTN_NEXT, row=1)
    async def page_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._navigate(interaction, delta=1)

    async def _navigate(self, interaction: discord.Interaction, delta: int) -> None:
        """Shared handler for ◀/▶: advance the page by ``delta`` and re-render the embed."""
        msg_id = interaction.message.id

        # Recover (page, total_pages) from the embed footer on first click after a restart.
        if msg_id not in _review_page_cache:
            embed = interaction.message.embeds[0] if interaction.message.embeds else None
            footer = embed.footer.text if embed and embed.footer else ""
            _review_page_cache[msg_id] = _parse_page_from_footer(footer or "") or (1, 1)

        current_page, total_pages = _review_page_cache[msg_id]
        new_page = current_page + delta

        if new_page < 1 or new_page > total_pages:
            await interaction.response.defer()
            return

        _review_page_cache[msg_id] = (new_page, total_pages)
        await interaction.response.defer()
        await update_review_embed(self.bot, interaction=interaction, page=new_page)


# ---------------------------------------------------------------------------
# Apply button embed builder
# ---------------------------------------------------------------------------


def build_apply_embed(form_name: str, description: str | None, lang: str = "en") -> discord.Embed:
    """Build the embed shown above the Apply button in the apply channel."""
    return discord.Embed(
        title=f"\U0001f4cb {form_name}",
        description=description or get_string(lang, "application.apply.default_description"),
        colour=discord.Colour.green(),
    )


# ---------------------------------------------------------------------------
# Apply button message lifecycle helpers
# ---------------------------------------------------------------------------


async def delete_apply_message(bot, channel_id: int, message_id: int) -> None:
    """Best-effort delete a single apply button message."""
    try:
        channel = await bot_get_or_fetch_channel(bot, channel_id)
        msg = await channel.fetch_message(message_id)
        await msg.delete()
    except discord.HTTPException:
        bot.log.warning("application: could not delete apply message %d in channel %d", message_id, channel_id)


async def post_apply_button_message(bot, form_id: int) -> None:
    """Post (or re-post) the Apply button message for a form.

    Reads form from DB, deletes old message if any, posts new one, updates ApplyMessageId.
    No-op if form lacks ApplyChannelId or isn't ready.
    """
    with bot.session_scope() as session:
        form = ApplicationForm.get_by_id(form_id, session)
        if form is None:
            return
        if not form.ApplyChannelId or not form.ReviewChannelId or not form.questions:
            return
        channel_id = form.ApplyChannelId
        old_message_id = form.ApplyMessageId
        form_name = form.Name
        description = form.ApplyDescription
        lang = bot.get_guild_language(form.GuildId)

    # Delete old message if it exists
    if old_message_id:
        await delete_apply_message(bot, channel_id, old_message_id)

    # Post new message
    channel = await bot_get_or_fetch_channel(bot, channel_id)
    if channel is None:
        bot.log.warning("application: could not fetch apply channel %d for form %d", channel_id, form_id)
        return

    embed = build_apply_embed(form_name, description, lang)
    view = ApplicationApplyView(bot=bot)
    view.apply_button.label = get_string(lang, "application.apply.button_label")
    msg = await channel.send(embed=embed, view=view)

    with bot.session_scope() as session:
        form = ApplicationForm.get_by_id(form_id, session)
        if form is not None:
            form.ApplyMessageId = msg.id


async def edit_apply_button_message(
    bot, form_id: int | None = None, *, preloaded: "ApplyEmbedData | None" = None
) -> None:
    """Edit the Apply button message in-place (e.g. after description change).

    Raises discord.HTTPException on failure — callers must catch.

    Pass ``preloaded`` to skip the database lookup (used by bulk language-refresh).
    """
    if preloaded is not None:
        channel_id = preloaded.channel_id
        message_id = preloaded.message_id
        form_name = preloaded.form_name
        description = preloaded.description
        lang = preloaded.lang
    else:
        with bot.session_scope() as session:
            form = ApplicationForm.get_by_id(form_id, session)
            if form is None or not form.ApplyMessageId or not form.ApplyChannelId:
                return
            channel_id = form.ApplyChannelId
            message_id = form.ApplyMessageId
            form_name = form.Name
            description = form.ApplyDescription
            lang = bot.get_guild_language(form.GuildId)

    try:
        channel = await bot_get_or_fetch_channel(bot, channel_id)
        msg = await channel.fetch_message(message_id)
        embed = build_apply_embed(form_name, description, lang)
        view = ApplicationApplyView(bot=bot)
        view.apply_button.label = get_string(lang, "application.apply.button_label")
        await msg.edit(embed=embed, view=view)
    except discord.HTTPException:
        bot.log.warning("application: could not edit apply message %d in channel %d", message_id, channel_id)
        raise


# ---------------------------------------------------------------------------
# Persistent apply view
# ---------------------------------------------------------------------------


class ApplicationApplyView(discord.ui.View):
    """Single-button persistent view posted in a public channel.

    One view instance (registered in ``setup_hook``) handles ALL apply messages
    across all guilds — the form is looked up via ``interaction.message.id``.
    """

    def __init__(self, bot=None):
        super().__init__(timeout=None)  # persistent — survives bot restarts
        self.bot = bot

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        if self.bot:
            self.bot.log.error("Error in ApplicationApplyView: %s", error, exc_info=error)
            lang = self.bot.get_guild_language(interaction.guild_id)
        else:
            lang = "en"
        await send_hidden_message(interaction, get_string(lang, "application.error_generic"))

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.green, custom_id=_BTN_APPLY)
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Look up form via apply message ID
        lang = self.bot.get_guild_language(interaction.guild_id)
        with self.bot.session_scope() as session:
            form = ApplicationForm.get_by_apply_message(interaction.message.id, session)
            if form is None:
                await interaction.response.send_message(
                    get_string(lang, "application.apply.not_available"), ephemeral=True
                )
                return

            # 2. Check form is ready
            if not form.ReviewChannelId:
                await interaction.response.send_message(get_string(lang, "application.apply.not_ready"), ephemeral=True)
                return

            # 3. Check no existing submission
            existing = ApplicationSubmission.get_by_user_and_form(interaction.user.id, form.Id, session)
            if existing:
                await interaction.response.send_message(
                    get_string(lang, "application.apply.already_applied", form=form.Name), ephemeral=True
                )
                return

            form_id = form.Id
            form_name = form.Name
            questions = [(q.Id, q.QuestionText) for q in form.questions]
            review_channel_id = form.ReviewChannelId

        # 4. Defer ephemeral
        await interaction.response.defer(ephemeral=True)

        # 5. Verify review channel accessible
        channel = await bot_get_or_fetch_channel(self.bot, review_channel_id)
        if channel is None:
            await interaction.followup.send(get_string(lang, "application.apply.review_unavailable"), ephemeral=True)
            return

        # 6. Start ApplicationSubmitConversation
        from modules.application.conversations import ApplicationSubmitConversation

        conv = ApplicationSubmitConversation(
            self.bot,
            interaction.user,
            interaction.guild,
            form_id=form_id,
            form_name=form_name,
            questions=questions,
        )
        try:
            await self.bot.convMan.init_conversation(conv)
        except discord.Forbidden:
            await interaction.followup.send(get_string(lang, "application.dm_forbidden"), ephemeral=True)
            return

        # 7. Send "Check your DMs!" followup
        await interaction.followup.send(get_string(lang, "application.check_dms"), ephemeral=True)
