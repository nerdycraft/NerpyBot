# -*- coding: utf-8 -*-
"""DM conversation flows for the application form system.

Three conversation subclasses:
- ApplicationCreateConversation — admin creates a new form by collecting questions
- ApplicationEditConversation — admin edits an existing form's questions
- ApplicationSubmitConversation — user answers a form's questions to submit an application
"""

from datetime import datetime, timezone
from enum import Enum

import discord
from discord import Embed

from models.application import (
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildConfig,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    SubmissionStatus,
)
from modules.views.application import ApplicationReviewView, build_review_embed
from utils.conversation import Conversation


# ---------------------------------------------------------------------------
# State enums
# ---------------------------------------------------------------------------


class CreateState(Enum):
    INIT = "init"
    COLLECT = "collect"
    DONE = "done"


class EditState(Enum):
    INIT = "init"
    ADD = "add"
    ADD_CONFIRM = "add_confirm"
    REMOVE = "remove"
    REMOVE_CONFIRM = "remove_confirm"
    REORDER = "reorder"
    REORDER_CONFIRM = "reorder_confirm"
    DONE = "done"


class SubmitState(Enum):
    INIT = "init"
    CONFIRM = "confirm"
    SUBMIT = "submit"
    CANCELLED = "cancelled"
    RESET = "reset"


class TemplateCreateState(Enum):
    INIT = "init"
    COLLECT = "collect"
    DONE = "done"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CANCEL_EMOJI = "\u274c"  # ❌
CONFIRM_EMOJI = "\u2705"  # ✅
BACK_EMOJI = "\u2b05\ufe0f"  # ⬅️
RESET_EMOJI = "\U0001f504"  # 🔄
ADD_EMOJI = "\U0001f4dd"  # 📝
REMOVE_EMOJI = "\U0001f5d1\ufe0f"  # 🗑️
REORDER_EMOJI = "\U0001f500"  # 🔀


def _questions_embed(title: str, questions: list[str], description: str | None = None) -> Embed:
    """Build an embed listing numbered questions."""
    lines = [f"**{i}.** {q}" for i, q in enumerate(questions, start=1)]
    body = "\n".join(lines) if lines else "_No questions yet._"
    if description:
        body = f"{description}\n\n{body}"
    return Embed(title=title, description=body)


# ---------------------------------------------------------------------------
# 1. ApplicationCreateConversation
# ---------------------------------------------------------------------------


class ApplicationCreateConversation(Conversation):
    """Walk an admin through creating a form by collecting questions one by one."""

    def __init__(
        self,
        bot,
        user,
        guild,
        form_name: str,
        review_channel_id: int,
        apply_channel_id: int | None = None,
        apply_description: str | None = None,
        required_approvals: int | None = None,
        required_denials: int | None = None,
        approval_message: str | None = None,
        denial_message: str | None = None,
    ):
        self.form_name = form_name
        self.review_channel_id = review_channel_id
        self.apply_channel_id = apply_channel_id
        self.apply_description = apply_description
        self.required_approvals = required_approvals
        self.required_denials = required_denials
        self.approval_message = approval_message
        self.denial_message = denial_message
        self.questions: list[str] = []
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        return {
            CreateState.INIT: self.state_init,
            CreateState.COLLECT: self.state_collect,
            CreateState.DONE: self.state_done,
        }

    async def state_init(self):
        emb = Embed(
            title=f"Creating form: {self.form_name}",
            description="Type your first question, or react " + CANCEL_EMOJI + " to finish.",
        )
        await self.send_both(emb, CreateState.COLLECT, self._handle_question, {CANCEL_EMOJI: CreateState.DONE})

    async def _handle_question(self, message):
        self.questions.append(message)
        return True

    async def state_collect(self):
        count = len(self.questions)
        emb = Embed(
            title=f"Creating form: {self.form_name}",
            description=f"Question {count} added. Type the next question, or react " + CANCEL_EMOJI + " to finish.",
        )
        await self.send_both(emb, CreateState.COLLECT, self._handle_question, {CANCEL_EMOJI: CreateState.DONE})

    async def state_done(self):
        if not self.questions:
            emb = Embed(title="Form creation cancelled", description="You need at least one question!")
            await self.send_ns(emb)
            await self.close()
            return

        with self.bot.session_scope() as session:
            form = ApplicationForm(
                GuildId=self.guild.id,
                Name=self.form_name,
                ReviewChannelId=self.review_channel_id,
                ApplyChannelId=self.apply_channel_id,
                ApplyDescription=self.apply_description,
                ApprovalMessage=self.approval_message,
                DenialMessage=self.denial_message,
            )
            if self.required_approvals is not None:
                form.RequiredApprovals = self.required_approvals
            if self.required_denials is not None:
                form.RequiredDenials = self.required_denials
            session.add(form)
            session.flush()
            for i, q_text in enumerate(self.questions, start=1):
                session.add(ApplicationQuestion(FormId=form.Id, QuestionText=q_text, SortOrder=i))
            form_id = form.Id

        if self.apply_channel_id:
            from modules.views.application import post_apply_button_message

            try:
                await post_apply_button_message(self.bot, form_id)
            except Exception:
                self.bot.log.error("application: failed to post apply button after form creation", exc_info=True)

        emb = _questions_embed(
            f"Form created: {self.form_name}",
            self.questions,
            description=f"Added {len(self.questions)} question(s).",
        )
        await self.send_ns(emb)
        await self.close()


class ApplicationTemplateCreateConversation(Conversation):
    """Walk an admin through creating a guild template by collecting questions one by one."""

    def __init__(
        self,
        bot,
        user,
        guild,
        template_name: str,
        approval_message: str | None = None,
        denial_message: str | None = None,
    ):
        self.template_name = template_name
        self.approval_message = approval_message
        self.denial_message = denial_message
        self.questions: list[str] = []
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        return {
            TemplateCreateState.INIT: self.state_init,
            TemplateCreateState.COLLECT: self.state_collect,
            TemplateCreateState.DONE: self.state_done,
        }

    async def state_init(self):
        emb = Embed(
            title=f"Creating template: {self.template_name}",
            description="Type your first question, or react " + CANCEL_EMOJI + " to finish.",
        )
        await self.send_both(
            emb, TemplateCreateState.COLLECT, self._handle_question, {CANCEL_EMOJI: TemplateCreateState.DONE}
        )

    async def _handle_question(self, message):
        self.questions.append(message)
        return True

    async def state_collect(self):
        count = len(self.questions)
        emb = Embed(
            title=f"Creating template: {self.template_name}",
            description=f"Question {count} added. Type the next question, or react " + CANCEL_EMOJI + " to finish.",
        )
        await self.send_both(
            emb, TemplateCreateState.COLLECT, self._handle_question, {CANCEL_EMOJI: TemplateCreateState.DONE}
        )

    async def state_done(self):
        if not self.questions:
            await self.send_ns(
                Embed(title="Template creation cancelled", description="You need at least one question.")
            )
            await self.close()
            return

        with self.bot.session_scope() as session:
            tpl = ApplicationTemplate(
                GuildId=self.guild.id,
                Name=self.template_name,
                IsBuiltIn=False,
                ApprovalMessage=self.approval_message,
                DenialMessage=self.denial_message,
            )
            session.add(tpl)
            session.flush()
            for i, q_text in enumerate(self.questions, start=1):
                session.add(ApplicationTemplateQuestion(TemplateId=tpl.Id, QuestionText=q_text, SortOrder=i))

        emb = _questions_embed(
            f"Template created: {self.template_name}",
            self.questions,
            description=f"Added {len(self.questions)} question(s).",
        )
        await self.send_ns(emb)
        await self.close()


# ---------------------------------------------------------------------------
# 2. ApplicationEditConversation
# ---------------------------------------------------------------------------


class ApplicationEditConversation(Conversation):
    """Let an admin add/remove/reorder questions on an existing form."""

    def __init__(self, bot, user, guild, form_id: int):
        self.form_id = form_id
        self.form_name: str = ""
        self._db_questions: list[tuple[int, str]] = []  # (id, text) loaded from DB
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        return {
            EditState.INIT: self.state_init,
            EditState.ADD: self.state_add,
            EditState.ADD_CONFIRM: self.state_add_confirm,
            EditState.REMOVE: self.state_remove,
            EditState.REMOVE_CONFIRM: self.state_remove_confirm,
            EditState.REORDER: self.state_reorder,
            EditState.REORDER_CONFIRM: self.state_reorder_confirm,
            EditState.DONE: self.state_done,
        }

    def _load_questions(self):
        """Reload questions from DB."""
        with self.bot.session_scope() as session:
            form = ApplicationForm.get_by_id(self.form_id, session)
            if form is None:
                return False
            self.form_name = form.Name
            self._db_questions = [(q.Id, q.QuestionText) for q in form.questions]
        return True

    def _question_texts(self) -> list[str]:
        return [text for _, text in self._db_questions]

    async def state_init(self):
        if not self._load_questions():
            emb = Embed(title="Error", description="Form not found.")
            await self.send_ns(emb)
            await self.close()
            return

        emb = _questions_embed(
            f"Editing form: {self.form_name}",
            self._question_texts(),
            description=(
                f"{ADD_EMOJI} = add question | {REMOVE_EMOJI} = remove question\n"
                f"{REORDER_EMOJI} = reorder | {CONFIRM_EMOJI} = done"
            ),
        )
        reactions = {
            ADD_EMOJI: EditState.ADD,
            REMOVE_EMOJI: EditState.REMOVE,
            REORDER_EMOJI: EditState.REORDER,
            CONFIRM_EMOJI: EditState.DONE,
        }
        await self.send_react(emb, reactions)

    async def state_add(self):
        emb = Embed(title="Add question", description="Type the new question:")
        await self.send_msg(emb, EditState.ADD_CONFIRM)

    async def state_add_confirm(self):
        new_text = self.lastResponse
        with self.bot.session_scope() as session:
            form = ApplicationForm.get_by_id(self.form_id, session)
            if form is None:
                emb = Embed(title="Error", description="This form no longer exists.")
                await self.send_ns(emb)
                await self.close()
                return
            max_order = max((q.SortOrder for q in form.questions), default=0)
            session.add(ApplicationQuestion(FormId=self.form_id, QuestionText=new_text, SortOrder=max_order + 1))

        # Transition back to INIT to show updated list
        self.currentState = EditState.INIT
        await self.state_init()

    async def state_remove(self):
        emb = Embed(title="Remove question", description="Which question number to remove?")
        await self.send_msg(emb, EditState.REMOVE_CONFIRM, self._validate_question_number)

    async def _validate_question_number(self, message):
        try:
            num = int(message)
        except ValueError:
            emb = Embed(title="Invalid input", description="Please enter a valid number.")
            await self.send_ns(emb)
            return False
        if num < 1 or num > len(self._db_questions):
            emb = Embed(
                title="Invalid number",
                description=f"Please enter a number between 1 and {len(self._db_questions)}.",
            )
            await self.send_ns(emb)
            return False
        return True

    async def state_remove_confirm(self):
        num = int(self.lastResponse)
        question_id = self._db_questions[num - 1][0]

        with self.bot.session_scope() as session:
            q = session.query(ApplicationQuestion).filter(ApplicationQuestion.Id == question_id).first()
            if q:
                session.delete(q)
                session.flush()
                # Reorder remaining questions
                form = ApplicationForm.get_by_id(self.form_id, session)
                if form is None:
                    emb = Embed(title="Error", description="This form no longer exists.")
                    await self.send_ns(emb)
                    await self.close()
                    return
                for i, question in enumerate(form.questions, start=1):
                    question.SortOrder = i

        self.currentState = EditState.INIT
        await self.state_init()

    async def state_reorder(self):
        emb = Embed(
            title="Reorder questions",
            description="Enter new order as comma-separated numbers (e.g., 3,1,2):",
        )
        await self.send_msg(emb, EditState.REORDER_CONFIRM, self._validate_reorder)

    async def _validate_reorder(self, message):
        try:
            nums = [int(x.strip()) for x in message.split(",")]
        except ValueError:
            emb = Embed(title="Invalid input", description="Please enter comma-separated numbers.")
            await self.send_ns(emb)
            return False

        expected = set(range(1, len(self._db_questions) + 1))
        if len(nums) != len(self._db_questions) or set(nums) != expected:
            emb = Embed(
                title="Invalid order",
                description=f"Please use each number from 1 to {len(self._db_questions)} exactly once.",
            )
            await self.send_ns(emb)
            return False
        return True

    async def state_reorder_confirm(self):
        nums = [int(x.strip()) for x in self.lastResponse.split(",")]

        with self.bot.session_scope() as session:
            form = ApplicationForm.get_by_id(self.form_id, session)
            if form is None:
                emb = Embed(title="Error", description="This form no longer exists.")
                await self.send_ns(emb)
                await self.close()
                return
            # Map old position (1-indexed) -> question object.
            # Use a two-phase update to avoid transient unique-constraint violations
            # when SQLite enforces the (FormId, SortOrder) constraint row-by-row:
            # first move all to a safe range, then assign the final positions.
            q_by_pos = {i: q for i, q in enumerate(form.questions, start=1)}
            offset = len(form.questions) + 1
            for q in q_by_pos.values():
                q.SortOrder += offset
            session.flush()
            for new_order, old_pos in enumerate(nums, start=1):
                q_by_pos[old_pos].SortOrder = new_order
            session.flush()

        self.currentState = EditState.INIT
        await self.state_init()

    async def state_done(self):
        emb = Embed(title="Editing complete", description=f"Finished editing form: {self.form_name}")
        await self.send_ns(emb)
        await self.close()


# ---------------------------------------------------------------------------
# 3. ApplicationSubmitConversation
# ---------------------------------------------------------------------------


class ApplicationSubmitConversation(Conversation):
    """Walk a user through answering a form's questions to create a submission."""

    def __init__(
        self,
        bot,
        user,
        guild,
        form_id: int,
        form_name: str,
        questions: list[tuple[int, str]],
    ):
        self.form_id = form_id
        self.form_name = form_name
        self.questions = questions  # [(question_id, question_text), ...]
        self.answers: dict[int, str] = {}  # question_id -> answer_text
        self.last_activity: datetime = datetime.now(timezone.utc)
        self.submission_id: int | None = None
        self._current_q_index: int = 0
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        handlers = {SubmitState.INIT: self.state_init}
        for i in range(len(self.questions)):
            # Use default-arg capture to bind *i* at definition time
            handlers[f"question_{i}"] = lambda idx=i: self.state_question(idx)
        handlers[SubmitState.CONFIRM] = self.state_confirm
        handlers[SubmitState.SUBMIT] = self.state_submit
        handlers[SubmitState.RESET] = self.state_reset
        handlers[SubmitState.CANCELLED] = self.state_cancelled
        return handlers

    async def on_message(self, message):
        self.last_activity = datetime.now(timezone.utc)
        await super().on_message(message)

    async def state_init(self):
        emb = Embed(
            title=self.form_name,
            description="I'll walk you through the questions.",
        )
        emb.set_footer(text=f"{CANCEL_EMOJI} cancel application")
        # Transition straight to first question
        self.currentState = "question_0"
        await self.send_ns(emb)
        await self.state_question(0)

    async def state_question(self, index: int):
        self._current_q_index = index
        q_id, q_text = self.questions[index]
        total = len(self.questions)

        existing_answer = self.answers.get(q_id)
        description = q_text
        if existing_answer:
            description += f"\n\n_Current answer: {existing_answer}_"

        emb = Embed(title=f"Question {index + 1}/{total}", description=description)
        emb.set_footer(text=f"{RESET_EMOJI} restart from Q1  |  {CANCEL_EMOJI} cancel application")

        next_state = f"question_{index + 1}" if index + 1 < total else SubmitState.CONFIRM
        reactions: dict = {}
        if index > 0:
            reactions[BACK_EMOJI] = f"question_{index - 1}"
        reactions[RESET_EMOJI] = SubmitState.RESET
        reactions[CANCEL_EMOJI] = SubmitState.CANCELLED
        await self.send_both(emb, next_state, self._handle_answer, reactions)

    async def _handle_answer(self, message):
        q_id, _ = self.questions[self._current_q_index]
        self.answers[q_id] = message
        return True

    async def state_reset(self):
        self.answers.clear()
        self.currentState = "question_0"
        await self.state_question(0)

    async def state_confirm(self):
        lines = []
        for q_id, q_text in self.questions:
            answer = self.answers.get(q_id, "_No answer_")
            lines.append(f"**Q:** {q_text}\n**A:** {answer}")
        body = "\n\n".join(lines)
        emb = Embed(
            title=f"Review: {self.form_name}",
            description=body + f"\n\n{CONFIRM_EMOJI} = submit | {CANCEL_EMOJI} = cancel",
        )
        await self.send_react(emb, {CONFIRM_EMOJI: SubmitState.SUBMIT, CANCEL_EMOJI: SubmitState.CANCELLED})

    async def state_submit(self):
        # Verify the review channel is still accessible before saving anything —
        # this catches the race condition where the channel was deleted while the
        # user was filling out the form.
        with self.bot.session_scope() as session:
            form = ApplicationForm.get_by_id(self.form_id, session)
            review_channel_id = form.ReviewChannelId if form else None

        channel = None
        if review_channel_id:
            channel = self.bot.get_channel(review_channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(review_channel_id)
                except (discord.NotFound, discord.Forbidden) as exc:
                    self.bot.log.error(
                        "application: review channel %d not accessible for form %r: %s",
                        review_channel_id,
                        self.form_name,
                        exc,
                    )
                    await self._notify_responsible(review_channel_id)
                    emb = Embed(
                        title="Submission error",
                        description=(
                            "Something went wrong reaching the review channel. "
                            "Your answers haven't been saved — please try again in a bit."
                        ),
                    )
                    await self.send_ns(emb)
                    await self.close()
                    return

        # Channel is accessible — save the submission and answers.
        with self.bot.session_scope() as session:
            submission = ApplicationSubmission(
                FormId=self.form_id,
                GuildId=self.guild.id,
                UserId=self.user.id,
                UserName=self.user.name,
                Status=SubmissionStatus.PENDING,
                SubmittedAt=datetime.now(timezone.utc),
            )
            session.add(submission)
            session.flush()
            self.submission_id = submission.Id

            for q_id, answer_text in self.answers.items():
                session.add(ApplicationAnswer(SubmissionId=submission.Id, QuestionId=q_id, AnswerText=answer_text))

        # Post review embed to the review channel.
        if channel is not None:
            with self.bot.session_scope() as session:
                submission = ApplicationSubmission.get_by_id(self.submission_id, session)
                form = ApplicationForm.get_by_id(self.form_id, session)
                embed = build_review_embed(submission, form, session)

            view = ApplicationReviewView(bot=self.bot)
            # Collect role IDs to mention: admin roles + configured manager/reviewer roles
            mention_ids: set[int] = {r.id for r in self.guild.roles if r.permissions.administrator}
            with self.bot.session_scope() as session:
                config = ApplicationGuildConfig.get(self.guild.id, session)
                if config:
                    if config.ManagerRoleId:
                        mention_ids.add(config.ManagerRoleId)
                    if config.ReviewerRoleId:
                        mention_ids.add(config.ReviewerRoleId)
            mention_content = " ".join(f"<@&{rid}>" for rid in sorted(mention_ids)) or None

            msg = await channel.send(content=mention_content, embed=embed, view=view)

            with self.bot.session_scope() as session:
                submission = ApplicationSubmission.get_by_id(self.submission_id, session)
                submission.ReviewMessageId = msg.id

        emb = Embed(title="Application submitted!", description="Your application has been submitted for review.")
        await self.send_ns(emb)
        await self.close()

    async def _notify_responsible(self, review_channel_id: int) -> None:
        """DM the guild owner when the review channel is unreachable mid-conversation."""
        try:
            owner = await self.bot.fetch_user(self.guild.owner_id)
            emb = Embed(
                title="Application review channel unreachable",
                description=(
                    f"Someone tried to submit an application for form **{self.form_name}** "
                    f"in **{self.guild.name}**, but the review channel (ID: `{review_channel_id}`) "
                    f"is not accessible to the bot.\n\n"
                    "The submission was not saved. Please check the channel permissions or reconfigure the form."
                ),
            )
            await owner.send(embed=emb)
        except (discord.Forbidden, discord.NotFound):
            self.bot.log.error(
                "application: could not DM guild owner %d about inaccessible review channel %d",
                self.guild.owner_id,
                review_channel_id,
                exc_info=True,
            )

    async def state_cancelled(self):
        emb = Embed(title="Application cancelled", description="Your application has been cancelled.")
        await self.send_ns(emb)
        await self.close()
