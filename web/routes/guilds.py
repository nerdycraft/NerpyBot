"""Guild management routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from web.cache import ValkeyClient
from web.dependencies import get_db_session, get_valkey, require_guild_access, require_premium
from web.schemas import (
    ApplicationAnswerSchema,
    ApplicationFormCreate,
    ApplicationVoteSchema,
    ApplicationFormSchema,
    CraftingRoleMappingUpdate,
    ApplicationFormUpdate,
    ApplicationQuestionCreate,
    ApplicationQuestionSchema,
    ApplicationQuestionUpdate,
    ApplicationSubmissionSchema,
    ApplicationTemplateCreate,
    ApplicationTemplateQuestionCreate,
    ApplicationTemplateQuestionSchema,
    ApplicationTemplateSchema,
    ApplicationTemplateUpdate,
    AutoDeleteCreate,
    AutoDeleteRule,
    AutoDeleteUpdate,
    AutoKickerConfig,
    AutoKickerUpdate,
    CraftingBoardSchema,
    CraftingOrderSchema,
    CraftingRoleMappingCreate,
    CraftingRoleMappingSchema,
    LanguageConfig,
    LanguageUpdate,
    LeaveMessageConfig,
    LeaveMessageUpdate,
    ModeratorRole,
    ModeratorRoleCreate,
    ReactionRoleEntrySchema,
    ReactionRoleMessageSchema,
    ReminderCreate,
    ReminderSchema,
    ReminderUpdate,
    RoleMappingCreate,
    RoleMappingSchema,
    WowCharacterMountSchema,
    WowGuildNewsCreate,
    WowGuildNewsSchema,
    WowGuildNewsUpdate,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/guilds", tags=["guilds"], dependencies=[Depends(require_premium)])


# ── Language ──


@router.get("/{guild_id}/language", response_model=LanguageConfig)
async def get_language(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Return the configured language for a guild (defaults to 'en')."""
    from models.admin import GuildLanguageConfig

    cfg = GuildLanguageConfig.get(guild_id, session)
    lang = cfg.Language if cfg else "en"
    return LanguageConfig(guild_id=str(guild_id), language=lang)


@router.put("/{guild_id}/language", response_model=LanguageConfig)
async def set_language(
    guild_id: int,
    body: LanguageUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Set or update the bot language for a guild."""
    from models.admin import GuildLanguageConfig

    cfg = GuildLanguageConfig.get(guild_id, session)
    if cfg is None:
        cfg = GuildLanguageConfig(GuildId=guild_id, Language=body.language)
        session.add(cfg)
    else:
        cfg.Language = body.language
    return LanguageConfig(guild_id=str(guild_id), language=cfg.Language)


# ── Moderator Roles ──


@router.get("/{guild_id}/moderator-roles", response_model=list[ModeratorRole])
async def list_moderator_roles(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List the configured moderator role(s) for a guild."""
    from models.admin import BotModeratorRole

    role = BotModeratorRole.get(guild_id, session)
    if role is None:
        return []
    return [ModeratorRole(guild_id=str(guild_id), role_id=str(role.RoleId))]


@router.post("/{guild_id}/moderator-roles", status_code=status.HTTP_201_CREATED)
async def add_moderator_role(
    guild_id: int,
    body: ModeratorRoleCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Set or replace the moderator role for a guild."""
    from models.admin import BotModeratorRole

    existing = BotModeratorRole.get(guild_id, session)
    if existing:
        existing.RoleId = int(body.role_id)
    else:
        role = BotModeratorRole(GuildId=guild_id, RoleId=int(body.role_id))
        session.add(role)
    return {"status": "created"}


@router.delete("/{guild_id}/moderator-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moderator_role(
    guild_id: int,
    role_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Remove the moderator role for a guild. Returns 404 if the role is not configured."""
    from models.admin import BotModeratorRole

    existing = BotModeratorRole.get(guild_id, session)
    if existing is None or existing.RoleId != role_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    BotModeratorRole.delete(guild_id, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Leave Messages ──


@router.get("/{guild_id}/leave-messages", response_model=LeaveMessageConfig)
async def get_leave_message(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Return the leave message configuration for a guild."""
    from models.leavemsg import LeaveMessage

    cfg = LeaveMessage.get(guild_id, session)
    if cfg is None:
        return LeaveMessageConfig(guild_id=str(guild_id), channel_id=None, message=None, enabled=False)
    return LeaveMessageConfig(
        guild_id=str(guild_id),
        channel_id=str(cfg.ChannelId) if cfg.ChannelId else None,
        message=cfg.Message,
        enabled=cfg.Enabled,
    )


@router.put("/{guild_id}/leave-messages", response_model=LeaveMessageConfig)
async def set_leave_message(
    guild_id: int,
    body: LeaveMessageUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create or update the leave message configuration for a guild."""
    from models.leavemsg import LeaveMessage

    cfg = LeaveMessage.get(guild_id, session)
    if cfg is None:
        cfg = LeaveMessage(GuildId=guild_id)
        session.add(cfg)
    if body.channel_id is not None:
        cfg.ChannelId = int(body.channel_id)
    if body.message is not None:
        cfg.Message = body.message
    if body.enabled is not None:
        cfg.Enabled = body.enabled
    return LeaveMessageConfig(
        guild_id=str(guild_id),
        channel_id=str(cfg.ChannelId) if cfg.ChannelId else None,
        message=cfg.Message,
        enabled=cfg.Enabled,
    )


# ── Auto Delete ──


@router.get("/{guild_id}/auto-delete", response_model=list[AutoDeleteRule])
async def list_auto_delete(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all auto-delete channel rules for a guild."""
    from models.moderation import AutoDelete

    rules = AutoDelete.get_by_guild(guild_id, session)
    return [
        AutoDeleteRule(
            id=r.Id,
            guild_id=str(guild_id),
            channel_id=str(r.ChannelId),
            keep_messages=r.KeepMessages or 0,
            delete_older_than=r.DeleteOlderThan or 0,
            delete_pinned=r.DeletePinnedMessage,
            enabled=r.Enabled,
        )
        for r in rules
    ]


@router.post("/{guild_id}/auto-delete", status_code=status.HTTP_201_CREATED, response_model=AutoDeleteRule)
async def create_auto_delete(
    guild_id: int,
    body: AutoDeleteCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create a new auto-delete rule for a channel. Returns 409 if a rule already exists for that channel."""
    from models.moderation import AutoDelete

    rule = AutoDelete(
        GuildId=guild_id,
        ChannelId=int(body.channel_id),
        KeepMessages=body.keep_messages,
        DeleteOlderThan=body.delete_older_than,
        DeletePinnedMessage=body.delete_pinned,
        Enabled=body.enabled,
    )
    session.add(rule)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Auto-delete rule already exists for this channel"
        )
    return AutoDeleteRule(
        id=rule.Id,
        guild_id=str(guild_id),
        channel_id=str(rule.ChannelId),
        keep_messages=rule.KeepMessages or 0,
        delete_older_than=rule.DeleteOlderThan or 0,
        delete_pinned=rule.DeletePinnedMessage,
        enabled=rule.Enabled,
    )


@router.put("/{guild_id}/auto-delete/{rule_id}", response_model=AutoDeleteRule)
async def update_auto_delete(
    guild_id: int,
    rule_id: int,
    body: AutoDeleteUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Update an existing auto-delete rule. Returns 404 if the rule does not belong to this guild."""
    from models.moderation import AutoDelete

    rule = session.query(AutoDelete).filter(AutoDelete.Id == rule_id, AutoDelete.GuildId == guild_id).first()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auto-delete rule not found")
    if body.keep_messages is not None:
        rule.KeepMessages = body.keep_messages
    if body.delete_older_than is not None:
        rule.DeleteOlderThan = body.delete_older_than
    if body.delete_pinned is not None:
        rule.DeletePinnedMessage = body.delete_pinned
    if body.enabled is not None:
        rule.Enabled = body.enabled
    return AutoDeleteRule(
        id=rule.Id,
        guild_id=str(guild_id),
        channel_id=str(rule.ChannelId),
        keep_messages=rule.KeepMessages or 0,
        delete_older_than=rule.DeleteOlderThan or 0,
        delete_pinned=rule.DeletePinnedMessage,
        enabled=rule.Enabled,
    )


@router.delete("/{guild_id}/auto-delete/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_auto_delete(
    guild_id: int,
    rule_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete an auto-delete rule. Returns 404 if not found for this guild."""
    from models.moderation import AutoDelete

    rule = session.query(AutoDelete).filter(AutoDelete.Id == rule_id, AutoDelete.GuildId == guild_id).first()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auto-delete rule not found")
    session.delete(rule)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Auto Kicker ──


@router.get("/{guild_id}/auto-kicker", response_model=AutoKickerConfig)
async def get_auto_kicker(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Return the auto-kicker configuration for a guild."""
    from models.moderation import AutoKicker

    cfg = AutoKicker.get_by_guild(guild_id, session)
    if cfg is None:
        return AutoKickerConfig(guild_id=str(guild_id), kick_after=0, enabled=False, reminder_message=None)
    return AutoKickerConfig(
        guild_id=str(guild_id),
        kick_after=cfg.KickAfter or 0,
        enabled=cfg.Enabled,
        reminder_message=cfg.ReminderMessage,
    )


@router.put("/{guild_id}/auto-kicker", response_model=AutoKickerConfig)
async def set_auto_kicker(
    guild_id: int,
    body: AutoKickerUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create or update the auto-kicker configuration for a guild."""
    from models.moderation import AutoKicker

    cfg = AutoKicker.get_by_guild(guild_id, session)
    if cfg is None:
        cfg = AutoKicker(GuildId=guild_id)
        session.add(cfg)
    if body.kick_after is not None:
        cfg.KickAfter = body.kick_after
    if body.enabled is not None:
        cfg.Enabled = body.enabled
    if body.reminder_message is not None:
        cfg.ReminderMessage = body.reminder_message
    return AutoKickerConfig(
        guild_id=str(guild_id),
        kick_after=cfg.KickAfter or 0,
        enabled=cfg.Enabled,
        reminder_message=cfg.ReminderMessage,
    )


# ── Reaction Roles (read-only) ──


@router.get("/{guild_id}/reaction-roles", response_model=list[ReactionRoleMessageSchema])
async def list_reaction_roles(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all reaction role messages configured for a guild (read-only)."""
    from models.reactionrole import ReactionRoleMessage

    messages = ReactionRoleMessage.get_by_guild(guild_id, session)
    return [
        ReactionRoleMessageSchema(
            id=m.Id,
            channel_id=str(m.ChannelId),
            message_id=str(m.MessageId),
            entries=[ReactionRoleEntrySchema(emoji=e.Emoji, role_id=str(e.RoleId)) for e in m.entries],
        )
        for m in messages
    ]


# ── Role Mappings ──


@router.get("/{guild_id}/role-mappings", response_model=list[RoleMappingSchema])
async def list_role_mappings(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all delegated role mappings for a guild."""
    from models.rolemanage import RoleMapping

    mappings = RoleMapping.get_by_guild(guild_id, session)
    return [
        RoleMappingSchema(
            id=m.Id,
            guild_id=str(guild_id),
            source_role_id=str(m.SourceRoleId),
            target_role_id=str(m.TargetRoleId),
        )
        for m in mappings
    ]


@router.post("/{guild_id}/role-mappings", status_code=status.HTTP_201_CREATED, response_model=RoleMappingSchema)
async def create_role_mapping(
    guild_id: int,
    body: RoleMappingCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create a new role mapping. Returns 409 if the mapping already exists."""
    from models.rolemanage import RoleMapping

    mapping = RoleMapping(
        GuildId=guild_id,
        SourceRoleId=int(body.source_role_id),
        TargetRoleId=int(body.target_role_id),
    )
    session.add(mapping)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role mapping already exists")
    return RoleMappingSchema(
        id=mapping.Id,
        guild_id=str(guild_id),
        source_role_id=str(mapping.SourceRoleId),
        target_role_id=str(mapping.TargetRoleId),
    )


@router.delete("/{guild_id}/role-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role_mapping(
    guild_id: int,
    mapping_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete a role mapping. Returns 404 if not found for this guild."""
    from models.rolemanage import RoleMapping

    mapping = session.query(RoleMapping).filter(RoleMapping.Id == mapping_id, RoleMapping.GuildId == guild_id).first()
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role mapping not found")
    session.delete(mapping)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Reminders ──


def _reminder_to_schema(r) -> ReminderSchema:
    return ReminderSchema(
        id=r.Id,
        channel_id=str(r.ChannelId),
        channel_name=r.ChannelName,
        author=r.Author,
        message=r.Message,
        enabled=r.Enabled,
        schedule_type=r.ScheduleType,
        next_fire=str(r.NextFire),
        count=r.Count or 0,
        interval_seconds=r.IntervalSeconds,
        schedule_time=r.ScheduleTime.strftime("%H:%M") if r.ScheduleTime else None,
        schedule_day_of_week=r.ScheduleDayOfWeek,
        schedule_day_of_month=r.ScheduleDayOfMonth,
        timezone=r.Timezone,
    )


@router.get("/{guild_id}/reminders", response_model=list[ReminderSchema])
async def list_reminders(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all reminder schedules for a guild."""
    from models.reminder import ReminderMessage

    return [_reminder_to_schema(r) for r in ReminderMessage.get_all_by_guild(guild_id, session)]


@router.post("/{guild_id}/reminders", response_model=ReminderSchema, status_code=status.HTTP_201_CREATED)
async def create_reminder(
    guild_id: int,
    body: ReminderCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create a new channel reminder schedule."""
    from datetime import UTC, datetime, time
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from models.reminder import ReminderMessage
    from utils.schedule import compute_next_fire

    try:
        tz = ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, KeyError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown timezone: {body.timezone}")

    schedule_time: time | None = None
    if body.schedule_time:
        try:
            h, m = body.schedule_time.split(":")
            schedule_time = time(int(h), int(m))
        except (ValueError, AttributeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="schedule_time must be HH:MM")

    if body.schedule_type == "interval" and not body.interval_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="interval_seconds required for interval type"
        )
    if body.schedule_type in ("daily", "weekly", "monthly") and schedule_time is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="schedule_time required for daily/weekly/monthly"
        )
    if body.schedule_type == "weekly" and body.schedule_day_of_week is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="schedule_day_of_week required for weekly type"
        )
    if body.schedule_type == "monthly" and body.schedule_day_of_month is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="schedule_day_of_month required for monthly type"
        )

    next_fire = compute_next_fire(
        body.schedule_type,
        interval_seconds=body.interval_seconds,
        schedule_time=schedule_time,
        schedule_day_of_week=body.schedule_day_of_week,
        schedule_day_of_month=body.schedule_day_of_month,
        timezone=tz,
    )

    reminder = ReminderMessage(
        GuildId=guild_id,
        ChannelId=int(body.channel_id),
        Message=body.message,
        Enabled=True,
        CreateDate=datetime.now(UTC),
        ScheduleType=body.schedule_type,
        IntervalSeconds=body.interval_seconds,
        ScheduleTime=schedule_time,
        ScheduleDayOfWeek=body.schedule_day_of_week,
        ScheduleDayOfMonth=body.schedule_day_of_month,
        Timezone=body.timezone if body.timezone != "UTC" else None,
        NextFire=next_fire,
    )
    session.add(reminder)
    session.flush()
    return _reminder_to_schema(reminder)


@router.patch("/{guild_id}/reminders/{reminder_id}", response_model=ReminderSchema)
async def update_reminder(
    guild_id: int,
    reminder_id: int,
    body: ReminderUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Update a reminder's message, channel, or enabled state."""
    from models.reminder import ReminderMessage

    r = ReminderMessage.get_by_id(reminder_id, guild_id, session)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    if body.message is not None:
        r.Message = body.message
    if body.enabled is not None:
        r.Enabled = body.enabled
    if body.channel_id is not None:
        r.ChannelId = int(body.channel_id)

    return _reminder_to_schema(r)


@router.delete("/{guild_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(
    guild_id: int,
    reminder_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete a reminder schedule."""
    from models.reminder import ReminderMessage

    r = ReminderMessage.get_by_id(reminder_id, guild_id, session)
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    session.delete(r)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Application Forms ──


def _submission_to_schema(s, question_texts: dict | None = None) -> ApplicationSubmissionSchema:
    return ApplicationSubmissionSchema(
        id=s.Id,
        form_name=s.form.Name if s.form else None,
        user_id=str(s.UserId),
        user_name=s.UserName,
        status=s.Status.value,
        submitted_at=str(s.SubmittedAt),
        decision_reason=s.DecisionReason,
        answers=[
            ApplicationAnswerSchema(
                question_id=a.QuestionId,
                question_text=(
                    question_texts.get(a.QuestionId, "")
                    if question_texts is not None
                    else (a.question.QuestionText if a.question else "")
                ),
                answer_text=a.AnswerText,
            )
            for a in s.answers
        ],
        votes=[
            ApplicationVoteSchema(
                voter_id=str(v.UserId),
                voter_name=v.VoterName,
                vote=v.Vote.value,
            )
            for v in s.votes
        ],
    )


def _form_to_schema(f) -> ApplicationFormSchema:
    return ApplicationFormSchema(
        id=f.Id,
        name=f.Name,
        review_channel_id=str(f.ReviewChannelId) if f.ReviewChannelId else None,
        required_approvals=f.RequiredApprovals,
        required_denials=f.RequiredDenials,
        approval_message=f.ApprovalMessage,
        denial_message=f.DenialMessage,
        apply_channel_id=str(f.ApplyChannelId) if f.ApplyChannelId else None,
        apply_description=f.ApplyDescription,
        questions=[
            ApplicationQuestionSchema(id=q.Id, question_text=q.QuestionText, sort_order=q.SortOrder)
            for q in f.questions
        ],
    )


@router.get("/{guild_id}/application-forms", response_model=list[ApplicationFormSchema])
async def list_application_forms(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all application forms with their questions for a guild."""
    from models.application import ApplicationForm

    return [_form_to_schema(f) for f in ApplicationForm.get_all_by_guild(guild_id, session)]


@router.post("/{guild_id}/application-forms", status_code=status.HTTP_201_CREATED, response_model=ApplicationFormSchema)
async def create_application_form(
    guild_id: int,
    body: ApplicationFormCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Create a new application form for a guild. Returns 409 if a form with that name already exists."""
    from models.application import ApplicationForm

    if ApplicationForm.get(body.name, guild_id, session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Form with this name already exists")
    form = ApplicationForm(
        GuildId=guild_id,
        Name=body.name,
        ReviewChannelId=int(body.review_channel_id) if body.review_channel_id else None,
        ApplyChannelId=int(body.apply_channel_id) if body.apply_channel_id else None,
        RequiredApprovals=body.required_approvals,
        RequiredDenials=body.required_denials,
        ApprovalMessage=body.approval_message,
        DenialMessage=body.denial_message,
        ApplyDescription=body.apply_description,
    )
    session.add(form)
    session.flush()
    schema = _form_to_schema(form)
    if form.ApplyChannelId:
        background_tasks.add_task(vk.send_bot_command, "post_apply_button", {"form_id": form.Id}, 1.0)
    return schema


@router.put("/{guild_id}/application-forms/{form_id}", response_model=ApplicationFormSchema)
async def update_application_form(
    guild_id: int,
    form_id: int,
    body: ApplicationFormUpdate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Update an existing application form. Returns 404 if not found for this guild."""
    from models.application import ApplicationForm

    form = (
        session.query(ApplicationForm)
        .filter(ApplicationForm.Id == form_id, ApplicationForm.GuildId == guild_id)
        .first()
    )
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    should_repost = False
    if body.name is not None:
        form.Name = body.name
    if body.required_approvals is not None:
        form.RequiredApprovals = body.required_approvals
    if body.required_denials is not None:
        form.RequiredDenials = body.required_denials
    if body.review_channel_id is not None:
        form.ReviewChannelId = int(body.review_channel_id) if body.review_channel_id else None
    if body.apply_channel_id is not None:
        new_id = int(body.apply_channel_id) if body.apply_channel_id else None
        if new_id != form.ApplyChannelId:
            form.ApplyChannelId = new_id
            should_repost = True
    if body.approval_message is not None:
        form.ApprovalMessage = body.approval_message
    if body.denial_message is not None:
        form.DenialMessage = body.denial_message
    if body.apply_description is not None:
        if body.apply_description != form.ApplyDescription:
            should_repost = True
        form.ApplyDescription = body.apply_description
    schema = _form_to_schema(form)
    if should_repost and form.ApplyChannelId:
        background_tasks.add_task(vk.send_bot_command, "post_apply_button", {"form_id": form.Id}, 1.0)
    return schema


@router.delete("/{guild_id}/application-forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application_form(
    guild_id: int,
    form_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete an application form and all its questions and submissions."""
    from models.application import ApplicationForm

    form = (
        session.query(ApplicationForm)
        .filter(ApplicationForm.Id == form_id, ApplicationForm.GuildId == guild_id)
        .first()
    )
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    session.delete(form)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{guild_id}/application-forms/{form_id}/questions",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationQuestionSchema,
)
async def add_form_question(
    guild_id: int,
    form_id: int,
    body: ApplicationQuestionCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Add a question to a form. Auto-assigns sort_order as max+1 if not provided."""
    from models.application import ApplicationForm, ApplicationQuestion

    form = (
        session.query(ApplicationForm)
        .filter(ApplicationForm.Id == form_id, ApplicationForm.GuildId == guild_id)
        .first()
    )
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    if body.sort_order is None:
        max_order = max((q.SortOrder for q in form.questions), default=0)
        sort_order = max_order + 1
    else:
        sort_order = body.sort_order
    question = ApplicationQuestion(FormId=form_id, QuestionText=body.question_text, SortOrder=sort_order)
    session.add(question)
    session.flush()
    return ApplicationQuestionSchema(id=question.Id, question_text=question.QuestionText, sort_order=question.SortOrder)


@router.put(
    "/{guild_id}/application-forms/{form_id}/questions/{question_id}",
    response_model=ApplicationQuestionSchema,
)
async def update_form_question(
    guild_id: int,
    form_id: int,
    question_id: int,
    body: ApplicationQuestionUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Update a question's text or sort order."""
    from models.application import ApplicationForm, ApplicationQuestion

    form = (
        session.query(ApplicationForm)
        .filter(ApplicationForm.Id == form_id, ApplicationForm.GuildId == guild_id)
        .first()
    )
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    question = (
        session.query(ApplicationQuestion)
        .filter(ApplicationQuestion.Id == question_id, ApplicationQuestion.FormId == form_id)
        .first()
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    if body.question_text is not None:
        question.QuestionText = body.question_text
    if body.sort_order is not None:
        question.SortOrder = body.sort_order
    return ApplicationQuestionSchema(id=question.Id, question_text=question.QuestionText, sort_order=question.SortOrder)


@router.delete(
    "/{guild_id}/application-forms/{form_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_form_question(
    guild_id: int,
    form_id: int,
    question_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete a question from a form."""
    from models.application import ApplicationForm, ApplicationQuestion

    form = (
        session.query(ApplicationForm)
        .filter(ApplicationForm.Id == form_id, ApplicationForm.GuildId == guild_id)
        .first()
    )
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    question = (
        session.query(ApplicationQuestion)
        .filter(ApplicationQuestion.Id == question_id, ApplicationQuestion.FormId == form_id)
        .first()
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    session.delete(question)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guild_id}/application-forms/{form_id}/submissions", response_model=list[ApplicationSubmissionSchema])
async def list_form_submissions(
    guild_id: int,
    form_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all submissions for a specific form."""
    from models.application import ApplicationForm, ApplicationSubmission

    form = (
        session.query(ApplicationForm)
        .filter(ApplicationForm.Id == form_id, ApplicationForm.GuildId == guild_id)
        .first()
    )
    if form is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
    submissions = (
        session.query(ApplicationSubmission)
        .filter(ApplicationSubmission.FormId == form_id)
        .order_by(ApplicationSubmission.Id.desc())
        .all()
    )
    question_texts = {q.Id: q.QuestionText for q in form.questions}
    return [_submission_to_schema(s, question_texts) for s in submissions]


# ── All Submissions (cross-form) ──


@router.get("/{guild_id}/application-submissions", response_model=list[ApplicationSubmissionSchema])
async def list_all_submissions(
    guild_id: int,
    form_id: int | None = None,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all submissions for a guild, optionally filtered by form."""
    from models.application import ApplicationAnswer, ApplicationSubmission

    q = (
        session.query(ApplicationSubmission)
        .filter(ApplicationSubmission.GuildId == guild_id)
        .options(joinedload(ApplicationSubmission.answers).joinedload(ApplicationAnswer.question))
    )
    if form_id is not None:
        q = q.filter(ApplicationSubmission.FormId == form_id)
    submissions = q.order_by(ApplicationSubmission.Id.desc()).all()
    return [_submission_to_schema(s) for s in submissions]


# ── Application Templates ──


def _template_to_schema(t) -> ApplicationTemplateSchema:
    return ApplicationTemplateSchema(
        id=t.Id,
        name=t.Name,
        is_built_in=t.IsBuiltIn,
        approval_message=t.ApprovalMessage,
        denial_message=t.DenialMessage,
        questions=[
            ApplicationTemplateQuestionSchema(id=q.Id, question_text=q.QuestionText, sort_order=q.SortOrder)
            for q in t.questions
        ],
    )


@router.get("/{guild_id}/application-templates", response_model=list[ApplicationTemplateSchema])
async def list_application_templates(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List built-in and guild-specific application templates."""
    from models.application import ApplicationTemplate

    return [_template_to_schema(t) for t in ApplicationTemplate.get_available(guild_id, session)]


@router.post(
    "/{guild_id}/application-templates", status_code=status.HTTP_201_CREATED, response_model=ApplicationTemplateSchema
)
async def create_application_template(
    guild_id: int,
    body: ApplicationTemplateCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create a guild-specific application template."""
    from models.application import ApplicationTemplate, ApplicationTemplateQuestion

    template = ApplicationTemplate(
        GuildId=guild_id,
        Name=body.name,
        IsBuiltIn=False,
        ApprovalMessage=body.approval_message,
        DenialMessage=body.denial_message,
    )
    session.add(template)
    session.flush()
    for i, text in enumerate(body.question_texts, start=1):
        session.add(ApplicationTemplateQuestion(TemplateId=template.Id, QuestionText=text, SortOrder=i))
    session.flush()
    session.refresh(template)
    return _template_to_schema(template)


@router.put("/{guild_id}/application-templates/{template_id}", response_model=ApplicationTemplateSchema)
async def update_application_template(
    guild_id: int,
    template_id: int,
    body: ApplicationTemplateUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Update a guild-specific template. Returns 403 for built-in templates."""
    from models.application import ApplicationTemplate

    template = (
        session.query(ApplicationTemplate)
        .filter(ApplicationTemplate.Id == template_id, ApplicationTemplate.GuildId == guild_id)
        .first()
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.IsBuiltIn:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Built-in templates cannot be modified")
    if body.name is not None:
        template.Name = body.name
    if body.approval_message is not None:
        template.ApprovalMessage = body.approval_message
    if body.denial_message is not None:
        template.DenialMessage = body.denial_message
    return _template_to_schema(template)


@router.delete("/{guild_id}/application-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application_template(
    guild_id: int,
    template_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete a guild-specific template. Returns 403 for built-in templates."""
    from models.application import ApplicationTemplate

    template = (
        session.query(ApplicationTemplate)
        .filter(ApplicationTemplate.Id == template_id, ApplicationTemplate.GuildId == guild_id)
        .first()
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.IsBuiltIn:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Built-in templates cannot be deleted")
    session.delete(template)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{guild_id}/application-templates/{template_id}/questions",
    status_code=status.HTTP_201_CREATED,
    response_model=ApplicationTemplateQuestionSchema,
)
async def add_template_question(
    guild_id: int,
    template_id: int,
    body: ApplicationTemplateQuestionCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Add a question to a guild template."""
    from models.application import ApplicationTemplate, ApplicationTemplateQuestion

    template = (
        session.query(ApplicationTemplate)
        .filter(ApplicationTemplate.Id == template_id, ApplicationTemplate.GuildId == guild_id)
        .first()
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.IsBuiltIn:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Built-in templates cannot be modified")
    max_order = max((q.SortOrder for q in template.questions), default=0)
    question = ApplicationTemplateQuestion(
        TemplateId=template_id, QuestionText=body.question_text, SortOrder=max_order + 1
    )
    session.add(question)
    session.flush()
    return ApplicationTemplateQuestionSchema(
        id=question.Id, question_text=question.QuestionText, sort_order=question.SortOrder
    )


@router.delete(
    "/{guild_id}/application-templates/{template_id}/questions/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_template_question(
    guild_id: int,
    template_id: int,
    question_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete a question from a guild template."""
    from models.application import ApplicationTemplate, ApplicationTemplateQuestion

    template = (
        session.query(ApplicationTemplate)
        .filter(ApplicationTemplate.Id == template_id, ApplicationTemplate.GuildId == guild_id)
        .first()
    )
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.IsBuiltIn:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Built-in templates cannot be modified")
    question = (
        session.query(ApplicationTemplateQuestion)
        .filter(ApplicationTemplateQuestion.Id == question_id, ApplicationTemplateQuestion.TemplateId == template_id)
        .first()
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    session.delete(question)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── WoW ──


def _wow_news_to_schema(cfg, tracked_characters: int = 0) -> "WowGuildNewsSchema":
    return WowGuildNewsSchema(
        id=cfg.Id,
        channel_id=str(cfg.ChannelId),
        wow_guild_name=cfg.WowGuildNameDisplay or cfg.WowGuildName,
        wow_realm_slug=cfg.WowRealmSlug,
        region=cfg.Region,
        enabled=cfg.Enabled,
        min_level=cfg.MinLevel,
        active_days=cfg.ActiveDays,
        last_activity=str(cfg.LastActivityTimestamp) if cfg.LastActivityTimestamp else None,
        tracked_characters=tracked_characters,
    )


@router.get("/{guild_id}/wow")
async def get_wow_config(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Return WoW guild news configs and crafting board config for a guild."""
    from sqlalchemy import func

    from models.wow import CraftingBoardConfig, WowCharacterMounts, WowGuildNewsConfig

    news_configs = WowGuildNewsConfig.get_all_by_guild(guild_id, session)
    crafting = CraftingBoardConfig.get_by_guild(guild_id, session)

    # Batch-load character counts to avoid N+1
    config_ids = [n.Id for n in news_configs]
    counts: dict[int, int] = {}
    if config_ids:
        rows = (
            session.query(WowCharacterMounts.ConfigId, func.count(WowCharacterMounts.Id))
            .filter(WowCharacterMounts.ConfigId.in_(config_ids))
            .group_by(WowCharacterMounts.ConfigId)
            .all()
        )
        counts = dict(rows)

    crafting_boards = []
    if crafting:
        crafting_boards = [
            CraftingBoardSchema(id=crafting.Id, channel_id=str(crafting.ChannelId), description=crafting.Description)
        ]

    return {
        "guild_news": [_wow_news_to_schema(n, counts.get(n.Id, 0)) for n in news_configs],
        "crafting_boards": crafting_boards,
    }


@router.post("/{guild_id}/wow/news-configs", status_code=status.HTTP_201_CREATED, response_model=WowGuildNewsSchema)
async def create_wow_news_config(
    guild_id: int,
    body: WowGuildNewsCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Create a WoW guild news tracker for a Discord guild. Returns 409 if already tracked."""
    from models.wow import WowGuildNewsConfig
    from utils.strings import get_guild_language

    normalized_name = " ".join(body.wow_guild_name.split())
    name_slug = normalized_name.lower().replace(" ", "-")
    if WowGuildNewsConfig.get_existing(guild_id, name_slug, body.wow_realm_slug, body.region, session):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already tracking this WoW guild")

    lang = get_guild_language(guild_id, session)
    cfg = WowGuildNewsConfig(
        GuildId=guild_id,
        ChannelId=int(body.channel_id),
        WowGuildName=name_slug,
        WowGuildNameDisplay=normalized_name,
        WowRealmSlug=body.wow_realm_slug,
        Region=body.region,
        Language=lang,
        ActiveDays=body.active_days,
        MinLevel=body.min_level,
        Enabled=True,
    )
    session.add(cfg)
    session.flush()
    return _wow_news_to_schema(cfg)


@router.patch("/{guild_id}/wow/news-configs/{config_id}", response_model=WowGuildNewsSchema)
async def update_wow_news_config(
    guild_id: int,
    config_id: int,
    body: WowGuildNewsUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Partial update for a WoW guild news tracker (channel, active_days, min_level, enabled)."""
    from sqlalchemy import func

    from models.wow import WowCharacterMounts, WowGuildNewsConfig

    cfg = WowGuildNewsConfig.get_by_id(config_id, guild_id, session)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    if body.channel_id is not None:
        cfg.ChannelId = int(body.channel_id)
    if body.active_days is not None:
        cfg.ActiveDays = body.active_days
    if body.min_level is not None:
        cfg.MinLevel = body.min_level
    if body.enabled is not None:
        cfg.Enabled = body.enabled

    count = (
        session.query(func.count(WowCharacterMounts.Id)).filter(WowCharacterMounts.ConfigId == config_id).scalar()
    ) or 0

    return _wow_news_to_schema(cfg, count)


@router.delete("/{guild_id}/wow/news-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wow_news_config(
    guild_id: int,
    config_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Delete a WoW guild news tracker and all associated character mount data."""
    from models.wow import WowGuildNewsConfig

    cfg = WowGuildNewsConfig.get_by_id(config_id, guild_id, session)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    WowGuildNewsConfig.delete(config_id, guild_id, session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guild_id}/wow/news-configs/{config_id}/roster", response_model=list[WowCharacterMountSchema])
async def get_wow_news_roster(
    guild_id: int,
    config_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Return the character mount roster for a WoW guild news tracker, sorted by mount count desc."""
    from models.wow import WowCharacterMounts, WowGuildNewsConfig

    cfg = WowGuildNewsConfig.get_by_id(config_id, guild_id, session)
    if cfg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")

    from utils.blizzard import parse_known_mounts

    entries = WowCharacterMounts.get_all_by_config(config_id, session)

    result = []
    for e in entries:
        try:
            known_ids, _last_count, _ = parse_known_mounts(e.KnownMountIds)
            mount_count = len(known_ids)
        except Exception:
            mount_count = 0
        result.append(
            WowCharacterMountSchema(
                character_name=e.CharacterName,
                realm_slug=e.RealmSlug,
                mount_count=mount_count,
                last_checked=str(e.LastChecked) if e.LastChecked else None,
            )
        )

    result.sort(key=lambda x: x.mount_count, reverse=True)
    return result


@router.get("/{guild_id}/wow/crafting-orders", response_model=list[CraftingOrderSchema])
async def list_crafting_orders(
    guild_id: int,
    status_filter: str | None = None,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
    vk: ValkeyClient = Depends(get_valkey),
):
    """List crafting orders for a guild. Optionally filter by status (open/completed/cancelled)."""
    from models.wow import CraftingOrder

    query = session.query(CraftingOrder).filter(CraftingOrder.GuildId == guild_id)
    if status_filter:
        query = query.filter(CraftingOrder.Status == status_filter)
    orders = query.order_by(CraftingOrder.Id.desc()).all()

    # Lazy backfill: resolve display names for orders created before name persistence was added.
    # On the first request that includes unnamed orders, we ask the bot for names and write them
    # back to the DB so future requests skip the Valkey call entirely.
    null_ids: set[int] = set()
    for o in orders:
        if o.CreatorName is None and o.CreatorId:
            null_ids.add(o.CreatorId)
        if o.CrafterName is None and o.CrafterId:
            null_ids.add(o.CrafterId)
    if null_ids:
        resolved = (
            await vk.send_bot_command("get_member_names", {"guild_id": guild_id, "user_ids": list(null_ids)}) or {}
        )
        if resolved:
            for o in orders:
                if o.CreatorName is None and o.CreatorId and str(o.CreatorId) in resolved:
                    o.CreatorName = resolved[str(o.CreatorId)]
                if o.CrafterName is None and o.CrafterId and str(o.CrafterId) in resolved:
                    o.CrafterName = resolved[str(o.CrafterId)]

    return [
        CraftingOrderSchema(
            id=o.Id,
            item_name=o.ItemName,
            icon_url=o.IconUrl,
            notes=o.Notes,
            status=o.Status,
            creator_id=str(o.CreatorId),
            creator_name=o.CreatorName,
            crafter_id=str(o.CrafterId) if o.CrafterId else None,
            crafter_name=o.CrafterName,
            create_date=str(o.CreateDate),
        )
        for o in orders
    ]


# ── Crafting Role Mappings ──


# Inverted CRAFTING_PROFESSIONS: maps profession_id -> name. Computed once at import time.
def _get_profession_name_by_id() -> dict:
    try:
        from utils.blizzard import CRAFTING_PROFESSIONS

        return {v: k for k, v in CRAFTING_PROFESSIONS.items()}
    except Exception:
        _log.warning("Could not load CRAFTING_PROFESSIONS — crafting role mapping routes will be non-functional")
        return {}


_PROFESSION_NAME_BY_ID: dict = _get_profession_name_by_id()


@router.get("/{guild_id}/wow/crafting-role-mappings", response_model=list[CraftingRoleMappingSchema])
async def list_crafting_role_mappings(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """List all crafting role mappings for a guild."""
    from models.wow import CraftingRoleMapping

    profession_name_by_id = _PROFESSION_NAME_BY_ID
    mappings = CraftingRoleMapping.get_by_guild(guild_id, session)
    return [
        CraftingRoleMappingSchema(
            id=m.Id,
            role_id=str(m.RoleId),
            profession_id=m.ProfessionId,
            profession_name=profession_name_by_id.get(m.ProfessionId, str(m.ProfessionId)),
        )
        for m in mappings
    ]


@router.post("/{guild_id}/wow/crafting-role-mappings", response_model=CraftingRoleMappingSchema, status_code=201)
async def create_crafting_role_mapping(
    guild_id: int,
    body: CraftingRoleMappingCreate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Add a role → profession mapping for a guild."""
    from models.wow import CraftingRoleMapping

    profession_name_by_id = _PROFESSION_NAME_BY_ID
    if body.profession_id not in profession_name_by_id:
        raise HTTPException(status_code=400, detail="Unknown profession")
    mapping = CraftingRoleMapping(GuildId=guild_id, RoleId=int(body.role_id), ProfessionId=body.profession_id)
    session.add(mapping)
    session.flush()
    return CraftingRoleMappingSchema(
        id=mapping.Id,
        role_id=str(mapping.RoleId),
        profession_id=mapping.ProfessionId,
        profession_name=profession_name_by_id.get(mapping.ProfessionId, str(mapping.ProfessionId)),
    )


@router.put("/{guild_id}/wow/crafting-role-mappings/{mapping_id}", response_model=CraftingRoleMappingSchema)
async def update_crafting_role_mapping(
    guild_id: int,
    mapping_id: int,
    body: CraftingRoleMappingUpdate,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Update the profession for a role mapping."""
    from models.wow import CraftingRoleMapping

    if body.profession_id not in _PROFESSION_NAME_BY_ID:
        raise HTTPException(status_code=400, detail="Unknown profession")
    mapping = (
        session.query(CraftingRoleMapping)
        .filter(CraftingRoleMapping.Id == mapping_id, CraftingRoleMapping.GuildId == guild_id)
        .first()
    )
    if mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    mapping.ProfessionId = body.profession_id
    session.flush()
    return CraftingRoleMappingSchema(
        id=mapping.Id,
        role_id=str(mapping.RoleId),
        profession_id=mapping.ProfessionId,
        profession_name=_PROFESSION_NAME_BY_ID[body.profession_id],
    )


@router.delete("/{guild_id}/wow/crafting-role-mappings/{mapping_id}", status_code=204)
async def delete_crafting_role_mapping(
    guild_id: int,
    mapping_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
    """Remove a role → profession mapping."""
    from models.wow import CraftingRoleMapping

    mapping = (
        session.query(CraftingRoleMapping)
        .filter(CraftingRoleMapping.Id == mapping_id, CraftingRoleMapping.GuildId == guild_id)
        .first()
    )
    if mapping is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    session.delete(mapping)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Discord entities (via bot bridge) ──


@router.get("/{guild_id}/discord/channels")
async def list_discord_channels(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Fetch the channel list for a guild from the bot via Valkey bridge."""
    result = await vk.send_bot_command("get_channels", {"guild_id": guild_id})
    return result or {"channels": []}


@router.get("/{guild_id}/discord/roles")
async def list_discord_roles(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Fetch the role list for a guild from the bot via Valkey bridge."""
    result = await vk.send_bot_command("get_roles", {"guild_id": guild_id})
    return result or {"roles": []}
