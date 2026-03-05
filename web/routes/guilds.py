"""Guild management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from web.dependencies import get_current_user, get_db_session, require_guild_access
from web.schemas import (
    AutoDeleteCreate,
    AutoDeleteRule,
    AutoDeleteUpdate,
    AutoKickerConfig,
    AutoKickerUpdate,
    LanguageConfig,
    LanguageUpdate,
    LeaveMessageConfig,
    LeaveMessageUpdate,
    ModeratorRole,
    ModeratorRoleCreate,
)

router = APIRouter(prefix="/guilds", tags=["guilds"])


# ── Guild list ──


@router.get("/")
async def list_guilds(user: dict = Depends(get_current_user)):
    """List guilds the current user can manage (from cached permissions)."""
    return {"guilds": [], "message": "Use /api/auth/me for full guild list"}


# ── Language ──


@router.get("/{guild_id}/language", response_model=LanguageConfig)
async def get_language(
    guild_id: int,
    user: dict = Depends(require_guild_access),
    session: Session = Depends(get_db_session),
):
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
    session.flush()
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
