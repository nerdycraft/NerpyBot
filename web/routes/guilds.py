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
