# -*- coding: utf-8 -*-
"""DM conversation flows for the application form system.

Three conversation subclasses:
- ApplicationCreateConversation — admin creates a new form by collecting questions
- ApplicationEditConversation — admin edits an existing form's questions
- ApplicationSubmitConversation — user answers a form's questions to submit an application
"""

from datetime import datetime, timezone
from enum import Enum
from functools import partial

import discord
from discord import Embed

from models.application import (
    ApplicationAnswer,
    ApplicationForm,
    ApplicationGuildRole,
    ApplicationQuestion,
    ApplicationSubmission,
    ApplicationTemplate,
    ApplicationTemplateQuestion,
    SubmissionStatus,
)
from modules.views.application import ApplicationReviewView, build_review_embed
from utils.conversation import Conversation
from utils.strings import get_string


# ---------------------------------------------------------------------------
# State enums
# ---------------------------------------------------------------------------


class CreateState(Enum):
    INIT = "init"
    COLLECT = "collect"
    BACK = "back"
    REVIEW = "review"
    EDIT_Q_SELECT = "edit_q_select"
    EDIT_Q = "edit_q"
    DONE = "done"
    CANCEL = "cancel"


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
    EDIT_SELECT = "edit_select"


class TemplateCreateState(Enum):
    INIT = "init"
    COLLECT = "collect"
    BACK = "back"
    REVIEW = "review"
    EDIT_Q_SELECT = "edit_q_select"
    EDIT_Q = "edit_q"
    DONE = "done"
    CANCEL = "cancel"


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
EDIT_EMOJI = "\u270f\ufe0f"  # ✏️
LEAVE_EMOJI = "\U0001f6aa"  # 🚪


def _questions_embed(title: str, questions: list[str], description: str | None = None) -> Embed:
    """Build an embed listing numbered questions."""
    lines = [f"**{i}.** {q}" for i, q in enumerate(questions, start=1)]
    body = "\n".join(lines) if lines else "_No questions yet._"
    if description:
        body = f"{description}\n\n{body}"
    return Embed(title=title, description=body)


async def _show_question_review(conv, locale_prefix, item_name, init_state, done_state, edit_state, cancel_state):
    """Show a question review embed with confirm/edit/cancel reactions, or loop back to init if empty."""
    if not conv.questions:
        conv.currentState = init_state
        await conv.state_init()
        return
    emb = _questions_embed(
        get_string(conv.lang, f"{locale_prefix}.review_title", name=item_name),
        conv.questions,
    )
    emb.set_footer(text=get_string(conv.lang, f"{locale_prefix}.review_footer"))
    await conv.send_react(
        emb,
        {
            CONFIRM_EMOJI: done_state,
            EDIT_EMOJI: edit_state,
            CANCEL_EMOJI: cancel_state,
        },
    )


async def _parse_question_number(
    conv, message: str, *, invalid_desc: str, out_of_range_desc: str, out_of_range_title_key: str = "invalid_title"
) -> int | None:
    """Parse and validate a 1-based question number; sends error embed and returns None on failure."""
    _e = "application.conversation.error"
    try:
        num = int(message)
    except ValueError:
        await conv.send_ns(Embed(title=get_string(conv.lang, f"{_e}.invalid_input_title"), description=invalid_desc))
        return None
    if num < 1 or num > len(conv.questions):
        await conv.send_ns(
            Embed(title=get_string(conv.lang, f"{_e}.{out_of_range_title_key}"), description=out_of_range_desc)
        )
        return None
    return num


async def _handle_edit_q_selection(conv, message: str, locale_prefix: str, edit_state) -> bool:
    """Parse a question number for editing; sets _edit_q_index and target state. Returns False always."""
    _c = locale_prefix
    num = await _parse_question_number(
        conv,
        message,
        invalid_desc=get_string(conv.lang, f"{_c}.edit_q_select_invalid"),
        out_of_range_desc=get_string(conv.lang, f"{_c}.edit_q_select_out_of_range", total=len(conv.questions)),
    )
    if num is None:
        return False
    conv._edit_q_index = num - 1
    conv.currentState = edit_state
    return False


async def _get_form_or_close(conv, session):
    """Look up form by conv.form_id; sends error and closes if gone. Returns form or None."""
    form = ApplicationForm.get_by_id(conv.form_id, session)
    if form is None:
        _e = "application.conversation.error"
        await conv.send_ns(
            Embed(
                title=get_string(conv.lang, f"{_e}.title"),
                description=get_string(conv.lang, f"{_e}.form_gone"),
            )
        )
        await conv.close()
        return None
    return form


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
        self._edit_q_index: int = 0
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        return {
            CreateState.INIT: self.state_init,
            CreateState.COLLECT: self.state_collect,
            CreateState.BACK: self.state_back,
            CreateState.REVIEW: self.state_review,
            CreateState.EDIT_Q_SELECT: self.state_edit_q_select,
            CreateState.EDIT_Q: self.state_edit_q,
            CreateState.DONE: self.state_done,
            CreateState.CANCEL: self.state_cancel,
        }

    async def state_init(self):
        # No questions yet — only cancel available (no back)
        _c = "application.conversation.create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.title", name=self.form_name),
            description=get_string(self.lang, f"{_c}.init_description"),
        )
        await self.send_both(emb, CreateState.COLLECT, self._handle_question, {CANCEL_EMOJI: CreateState.CANCEL})

    async def _handle_question(self, message):
        self.questions.append(message)
        return True

    async def state_collect(self):
        count = len(self.questions)
        reactions = {CONFIRM_EMOJI: CreateState.REVIEW, CANCEL_EMOJI: CreateState.CANCEL}
        if count > 0:
            reactions[BACK_EMOJI] = CreateState.BACK
        _c = "application.conversation.create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.title", name=self.form_name),
            description=get_string(self.lang, f"{_c}.collect_description", count=count),
        )
        await self.send_both(emb, CreateState.COLLECT, self._handle_question, reactions)

    async def state_back(self):
        if self.questions:
            self.questions.pop()
        if self.questions:
            self.currentState = CreateState.COLLECT
            await self.state_collect()
        else:
            self.currentState = CreateState.INIT
            await self.state_init()

    async def state_review(self):
        await _show_question_review(
            self,
            "application.conversation.create",
            self.form_name,
            CreateState.INIT,
            CreateState.DONE,
            CreateState.EDIT_Q_SELECT,
            CreateState.CANCEL,
        )

    async def state_edit_q_select(self):
        total = len(self.questions)
        if total == 0:
            self.currentState = CreateState.INIT
            await self.state_init()
            return
        _c = "application.conversation.create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.edit_q_select_title"),
            description=get_string(self.lang, f"{_c}.edit_q_select_description", total=total),
        )
        await self.send_msg(
            emb,
            CreateState.EDIT_Q_SELECT,
            partial(
                _handle_edit_q_selection,
                self,
                locale_prefix="application.conversation.create",
                edit_state=CreateState.EDIT_Q,
            ),
        )

    async def state_edit_q(self):
        _c = "application.conversation.create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.edit_q_title", num=self._edit_q_index + 1),
            description=get_string(self.lang, f"{_c}.edit_q_description", current=self.questions[self._edit_q_index]),
        )
        await self.send_msg(emb, CreateState.EDIT_Q, self._handle_edit_q)

    async def _handle_edit_q(self, message):
        self.questions[self._edit_q_index] = message
        self.currentState = CreateState.REVIEW
        return False

    async def state_done(self):
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
            except discord.HTTPException:
                self.bot.log.error("application: failed to post apply button after form creation", exc_info=True)

        _c = "application.conversation.create"
        emb = _questions_embed(
            get_string(self.lang, f"{_c}.done_title", name=self.form_name),
            self.questions,
            description=get_string(self.lang, f"{_c}.done_description", count=len(self.questions)),
        )
        await self.send_ns(emb)
        await self.close()

    async def state_cancel(self):
        _c = "application.conversation.create"
        await self.send_ns(
            Embed(
                title=get_string(self.lang, f"{_c}.cancel_title"),
                description=get_string(self.lang, f"{_c}.cancel_description"),
            )
        )
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
        self._edit_q_index: int = 0
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        return {
            TemplateCreateState.INIT: self.state_init,
            TemplateCreateState.COLLECT: self.state_collect,
            TemplateCreateState.BACK: self.state_back,
            TemplateCreateState.REVIEW: self.state_review,
            TemplateCreateState.EDIT_Q_SELECT: self.state_edit_q_select,
            TemplateCreateState.EDIT_Q: self.state_edit_q,
            TemplateCreateState.DONE: self.state_done,
            TemplateCreateState.CANCEL: self.state_cancel,
        }

    async def state_init(self):
        _c = "application.conversation.template_create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.title", name=self.template_name),
            description=get_string(self.lang, f"{_c}.init_description"),
        )
        await self.send_both(
            emb, TemplateCreateState.COLLECT, self._handle_question, {CANCEL_EMOJI: TemplateCreateState.CANCEL}
        )

    async def _handle_question(self, message):
        self.questions.append(message)
        return True

    async def state_collect(self):
        count = len(self.questions)
        reactions = {CONFIRM_EMOJI: TemplateCreateState.REVIEW, CANCEL_EMOJI: TemplateCreateState.CANCEL}
        if count > 0:
            reactions[BACK_EMOJI] = TemplateCreateState.BACK
        _c = "application.conversation.template_create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.title", name=self.template_name),
            description=get_string(self.lang, f"{_c}.collect_description", count=count),
        )
        await self.send_both(emb, TemplateCreateState.COLLECT, self._handle_question, reactions)

    async def state_back(self):
        if self.questions:
            self.questions.pop()
        if self.questions:
            self.currentState = TemplateCreateState.COLLECT
            await self.state_collect()
        else:
            self.currentState = TemplateCreateState.INIT
            await self.state_init()

    async def state_review(self):
        await _show_question_review(
            self,
            "application.conversation.template_create",
            self.template_name,
            TemplateCreateState.INIT,
            TemplateCreateState.DONE,
            TemplateCreateState.EDIT_Q_SELECT,
            TemplateCreateState.CANCEL,
        )

    async def state_edit_q_select(self):
        total = len(self.questions)
        if total == 0:
            self.currentState = TemplateCreateState.INIT
            await self.state_init()
            return
        _c = "application.conversation.template_create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.edit_q_select_title"),
            description=get_string(self.lang, f"{_c}.edit_q_select_description", total=total),
        )
        await self.send_msg(
            emb,
            TemplateCreateState.EDIT_Q_SELECT,
            partial(
                _handle_edit_q_selection,
                self,
                locale_prefix="application.conversation.template_create",
                edit_state=TemplateCreateState.EDIT_Q,
            ),
        )

    async def state_edit_q(self):
        _c = "application.conversation.template_create"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.edit_q_title", num=self._edit_q_index + 1),
            description=get_string(self.lang, f"{_c}.edit_q_description", current=self.questions[self._edit_q_index]),
        )
        await self.send_msg(emb, TemplateCreateState.EDIT_Q, self._handle_edit_q)

    async def _handle_edit_q(self, message):
        self.questions[self._edit_q_index] = message
        self.currentState = TemplateCreateState.REVIEW
        return False

    async def state_done(self):
        _c = "application.conversation.template_create"
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
            get_string(self.lang, f"{_c}.done_title", name=self.template_name),
            self.questions,
            description=get_string(self.lang, f"{_c}.done_description", count=len(self.questions)),
        )
        await self.send_ns(emb)
        await self.close()

    async def state_cancel(self):
        _c = "application.conversation.template_create"
        await self.send_ns(
            Embed(
                title=get_string(self.lang, f"{_c}.cancel_title"),
                description=get_string(self.lang, f"{_c}.cancel_description"),
            )
        )
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
        _c = "application.conversation.edit"
        _e = "application.conversation.error"
        if not self._load_questions():
            emb = Embed(
                title=get_string(self.lang, f"{_e}.title"),
                description=get_string(self.lang, f"{_e}.form_not_found"),
            )
            await self.send_ns(emb)
            await self.close()
            return

        emb = _questions_embed(
            get_string(self.lang, f"{_c}.title", name=self.form_name),
            self._question_texts(),
            description=get_string(self.lang, f"{_c}.init_description"),
        )
        reactions = {
            ADD_EMOJI: EditState.ADD,
            REMOVE_EMOJI: EditState.REMOVE,
            REORDER_EMOJI: EditState.REORDER,
            CONFIRM_EMOJI: EditState.DONE,
        }
        await self.send_react(emb, reactions)

    async def state_add(self):
        _c = "application.conversation.edit"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.add_title"),
            description=get_string(self.lang, f"{_c}.add_description"),
        )
        await self.send_msg(emb, EditState.ADD_CONFIRM)

    async def state_add_confirm(self):
        _e = "application.conversation.error"
        new_text = self.lastResponse
        with self.bot.session_scope() as session:
            form = ApplicationForm.get_by_id(self.form_id, session)
            if form is None:
                emb = Embed(
                    title=get_string(self.lang, f"{_e}.title"),
                    description=get_string(self.lang, f"{_e}.form_gone"),
                )
                await self.send_ns(emb)
                await self.close()
                return
            max_order = max((q.SortOrder for q in form.questions), default=0)
            session.add(ApplicationQuestion(FormId=self.form_id, QuestionText=new_text, SortOrder=max_order + 1))

        # Transition back to INIT to show updated list
        self.currentState = EditState.INIT
        await self.state_init()

    async def state_remove(self):
        _c = "application.conversation.edit"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.remove_title"),
            description=get_string(self.lang, f"{_c}.remove_description"),
        )
        await self.send_msg(emb, EditState.REMOVE_CONFIRM, self._validate_question_number)

    async def _validate_question_number(self, message):
        _c = "application.conversation.edit"
        _e = "application.conversation.error"
        try:
            num = int(message)
        except ValueError:
            emb = Embed(
                title=get_string(self.lang, f"{_e}.invalid_input_title"),
                description=get_string(self.lang, f"{_c}.invalid_number_description"),
            )
            await self.send_ns(emb)
            return False
        if num < 1 or num > len(self._db_questions):
            emb = Embed(
                title=get_string(self.lang, f"{_e}.invalid_number_title"),
                description=get_string(self.lang, f"{_c}.out_of_range_description", total=len(self._db_questions)),
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
                form = await _get_form_or_close(self, session)
                if form is None:
                    return
                for i, question in enumerate(form.questions, start=1):
                    question.SortOrder = i

        self.currentState = EditState.INIT
        await self.state_init()

    async def state_reorder(self):
        _c = "application.conversation.edit"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.reorder_title"),
            description=get_string(self.lang, f"{_c}.reorder_description"),
        )
        await self.send_msg(emb, EditState.REORDER_CONFIRM, self._validate_reorder)

    async def _validate_reorder(self, message):
        _c = "application.conversation.edit"
        _e = "application.conversation.error"
        try:
            nums = [int(x.strip()) for x in message.split(",")]
        except ValueError:
            emb = Embed(
                title=get_string(self.lang, f"{_e}.invalid_input_title"),
                description=get_string(self.lang, f"{_c}.reorder_invalid_input"),
            )
            await self.send_ns(emb)
            return False

        expected = set(range(1, len(self._db_questions) + 1))
        if len(nums) != len(self._db_questions) or set(nums) != expected:
            emb = Embed(
                title=get_string(self.lang, f"{_e}.invalid_order_title"),
                description=get_string(self.lang, f"{_c}.reorder_invalid_order", total=len(self._db_questions)),
            )
            await self.send_ns(emb)
            return False
        return True

    async def state_reorder_confirm(self):
        nums = [int(x.strip()) for x in self.lastResponse.split(",")]

        with self.bot.session_scope() as session:
            form = await _get_form_or_close(self, session)
            if form is None:
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
        _c = "application.conversation.edit"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.done_title"),
            description=get_string(self.lang, f"{_c}.done_description", name=self.form_name),
        )
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
        self._editing: bool = False
        super().__init__(bot, user, guild)

    def create_state_handler(self):
        handlers = {SubmitState.INIT: self.state_init}
        for i in range(len(self.questions)):
            # Use default-arg capture to bind *i* at definition time
            handlers[f"question_{i}"] = lambda idx=i: self.state_question(idx)
        handlers[SubmitState.CONFIRM] = self.state_confirm
        handlers[SubmitState.SUBMIT] = self.state_submit
        handlers[SubmitState.RESET] = self.state_reset
        handlers[SubmitState.EDIT_SELECT] = self.state_edit_select
        handlers[SubmitState.CANCELLED] = self.state_cancelled
        return handlers

    async def on_message(self, message):
        self.last_activity = datetime.now(timezone.utc)
        await super().on_message(message)

    async def state_init(self):
        _c = "application.conversation.submit"
        emb = Embed(
            title=self.form_name,
            description=get_string(self.lang, f"{_c}.init_description"),
        )
        emb.set_footer(text=get_string(self.lang, f"{_c}.init_footer"))
        # Transition straight to first question
        self.currentState = "question_0"
        await self.send_ns(emb)
        await self.state_question(0)

    async def state_question(self, index: int):
        _c = "application.conversation.submit"
        self._current_q_index = index
        q_id, q_text = self.questions[index]
        total = len(self.questions)

        existing_answer = self.answers.get(q_id)
        description = q_text
        if existing_answer:
            description += get_string(self.lang, f"{_c}.current_answer", answer=existing_answer)

        emb = Embed(
            title=get_string(self.lang, f"{_c}.question_title", num=index + 1, total=total),
            description=description,
        )

        if self._editing:
            next_state = SubmitState.CONFIRM
            emb.set_footer(text=get_string(self.lang, f"{_c}.question_footer_editing"))
            reactions = {BACK_EMOJI: SubmitState.CONFIRM, LEAVE_EMOJI: SubmitState.CANCELLED}
        else:
            next_state = f"question_{index + 1}" if index + 1 < total else SubmitState.CONFIRM
            reactions: dict = {}
            if index > 0:
                reactions[BACK_EMOJI] = f"question_{index - 1}"
                reactions[RESET_EMOJI] = SubmitState.RESET
                emb.set_footer(text=get_string(self.lang, f"{_c}.question_footer_restart"))
            else:
                emb.set_footer(text=get_string(self.lang, f"{_c}.question_footer_leave"))
            reactions[LEAVE_EMOJI] = SubmitState.CANCELLED

        await self.send_both(emb, next_state, self._handle_answer, reactions)

    async def _handle_answer(self, message):
        q_id, _ = self.questions[self._current_q_index]
        self.answers[q_id] = message
        self._editing = False
        return True

    async def state_reset(self):
        self.answers.clear()
        self._editing = False
        self.currentState = "question_0"
        await self.state_question(0)

    async def state_edit_select(self):
        _c = "application.conversation.submit"
        total = len(self.questions)
        emb = Embed(
            title=get_string(self.lang, f"{_c}.edit_select_title"),
            description=get_string(self.lang, f"{_c}.edit_select_description", total=total),
        )
        await self.send_msg(emb, SubmitState.EDIT_SELECT, self._handle_edit_select)

    async def _handle_edit_select(self, message):
        _c = "application.conversation.submit"
        num = await _parse_question_number(
            self,
            message,
            invalid_desc=get_string(self.lang, f"{_c}.edit_select_invalid"),
            out_of_range_desc=get_string(self.lang, f"{_c}.edit_select_out_of_range", total=len(self.questions)),
            out_of_range_title_key="invalid_number_title",
        )
        if num is None:
            return False
        self._editing = True
        self.currentState = f"question_{num - 1}"
        return False

    async def state_confirm(self):
        _c = "application.conversation.submit"
        self._editing = False
        lines = []
        for q_id, q_text in self.questions:
            answer = self.answers.get(q_id) or get_string(self.lang, f"{_c}.confirm_no_answer")
            lines.append(get_string(self.lang, f"{_c}.confirm_qa_line", question=q_text, answer=answer))
        body = "\n\n".join(lines)
        emb = Embed(
            title=get_string(self.lang, f"{_c}.confirm_title", name=self.form_name),
            description=body,
        )
        emb.set_footer(text=get_string(self.lang, f"{_c}.confirm_footer"))
        await self.send_react(
            emb,
            {
                CONFIRM_EMOJI: SubmitState.SUBMIT,
                EDIT_EMOJI: SubmitState.EDIT_SELECT,
                LEAVE_EMOJI: SubmitState.CANCELLED,
            },
        )

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
                    _c = "application.conversation.submit"
                    emb = Embed(
                        title=get_string(self.lang, f"{_c}.error_title"),
                        description=get_string(self.lang, f"{_c}.error_description"),
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
                lang = self.lang
                embed = build_review_embed(submission, form, session, lang)
                # Collect role IDs to mention: non-managed admin roles + all configured manager/reviewer roles
                mention_ids: set[int] = {
                    r.id for r in self.guild.roles if r.permissions.administrator and not r.managed
                }
                guild_roles = (
                    session.query(ApplicationGuildRole).filter(ApplicationGuildRole.GuildId == self.guild.id).all()
                )
                for gr in guild_roles:
                    mention_ids.add(gr.RoleId)
                submission_user_name = submission.UserName

            view = ApplicationReviewView(bot=self.bot)
            mention_content = " ".join(f"<@&{rid}>" for rid in sorted(mention_ids)) or None

            msg = await channel.send(embed=embed, view=view)

            thread_name = submission_user_name or get_string(
                self.lang, "application.conversation.submit.review_thread_name"
            )
            try:
                thread = await msg.create_thread(name=thread_name)
                if mention_content:
                    await thread.send(mention_content)
            except discord.HTTPException:
                self.bot.log.warning(
                    "application: failed to create review thread for msg %d", msg.id
                )

            with self.bot.session_scope() as session:
                submission = ApplicationSubmission.get_by_id(self.submission_id, session)
                submission.ReviewMessageId = msg.id

        _c = "application.conversation.submit"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.submitted_title"),
            description=get_string(self.lang, f"{_c}.submitted_description"),
        )
        await self.send_ns(emb)
        await self.close()

    async def _notify_responsible(self, review_channel_id: int) -> None:
        """DM the guild owner when the review channel is unreachable mid-conversation."""
        _c = "application.conversation.submit"
        try:
            owner = await self.bot.fetch_user(self.guild.owner_id)
            emb = Embed(
                title=get_string(self.lang, f"{_c}.channel_unreachable_title"),
                description=get_string(
                    self.lang,
                    f"{_c}.channel_unreachable_description",
                    form=self.form_name,
                    guild=self.guild.name,
                    channel_id=review_channel_id,
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
        _c = "application.conversation.submit"
        emb = Embed(
            title=get_string(self.lang, f"{_c}.cancelled_title"),
            description=get_string(self.lang, f"{_c}.cancelled_description"),
        )
        await self.send_ns(emb)
        await self.close()
