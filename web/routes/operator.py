"""Operator routes — health, module management."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from web.dependencies import get_db_session, get_valkey, require_operator
from web.schemas import (
    BotGuildInfo,
    BotGuildListResponse,
    HealthResponse,
    ModuleActionResponse,
    ModuleListResponse,
    PremiumUserGrant,
    PremiumUserSchema,
    VoiceConnectionDetail,
)
from web.cache import ValkeyClient

router = APIRouter(prefix="/operator", tags=["operator"])


# ── Premium user management ──


def _premium_to_schema(p) -> PremiumUserSchema:
    return PremiumUserSchema(
        user_id=str(p.UserId),
        granted_at=str(p.GrantedAt),
        granted_by=str(p.GrantedByUserId) if p.GrantedByUserId else None,
    )


@router.get("/premium-users", response_model=list[PremiumUserSchema])
async def list_premium_users(
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """List all users who have been granted premium dashboard access."""
    from models.admin import PremiumUser

    return [_premium_to_schema(p) for p in PremiumUser.get_all(session)]


@router.post("/premium-users", response_model=PremiumUserSchema, status_code=http_status.HTTP_201_CREATED)
async def grant_premium(
    body: PremiumUserGrant,
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """Grant premium dashboard access to a user."""
    from models.admin import PremiumUser

    try:
        target_user_id = int(body.user_id)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="user_id must be a valid integer"
        )
    entry = PremiumUser.grant(target_user_id, int(user["sub"]), session)
    return _premium_to_schema(entry)


@router.delete("/premium-users/{user_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def revoke_premium(
    user_id: int,
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """Revoke premium dashboard access from a user."""
    from models.admin import PremiumUser

    if not PremiumUser.revoke(user_id, session):
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="User not found in premium list")


# ── Bot health and modules ──


@router.get("/health", response_model=HealthResponse)
async def health(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Request health metrics from the bot via Valkey."""
    result = await vk.send_bot_command("health", {})
    if result is None:
        return HealthResponse(status="unreachable")
    return HealthResponse(
        status="online",
        uptime_seconds=result.get("uptime_seconds"),
        latency_ms=result.get("latency_ms"),
        guild_count=result.get("guild_count"),
        voice_connections=result.get("voice_connections"),
        active_reminders=result.get("active_reminders"),
        error_count_24h=result.get("error_count_24h"),
        memory_mb=result.get("memory_mb"),
        cpu_percent=result.get("cpu_percent"),
        python_version=result.get("python_version"),
        discord_py_version=result.get("discord_py_version"),
        bot_version=result.get("bot_version"),
        voice_details=[VoiceConnectionDetail(**d) for d in result.get("voice_details", [])],
    )


@router.get("/modules", response_model=ModuleListResponse)
async def list_modules(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Request loaded modules from the bot."""
    result = await vk.send_bot_command("list_modules", {})
    if result is None:
        return ModuleListResponse(modules=[], status="bot unreachable")
    return ModuleListResponse(modules=result.get("modules", []))


@router.post("/modules/{name}/load", response_model=ModuleActionResponse)
async def load_module(
    name: str,
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Load a module on the bot."""
    result = await vk.send_bot_command("module_load", {"module": name})
    if result is None:
        return ModuleActionResponse(module=name, action="load", success=False, error="Bot unreachable")
    return ModuleActionResponse(module=name, action="load", **result)


@router.post("/modules/{name}/unload", response_model=ModuleActionResponse)
async def unload_module(
    name: str,
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Unload a module on the bot."""
    result = await vk.send_bot_command("module_unload", {"module": name})
    if result is None:
        return ModuleActionResponse(module=name, action="unload", success=False, error="Bot unreachable")
    return ModuleActionResponse(module=name, action="unload", **result)


@router.get("/guilds", response_model=BotGuildListResponse)
async def list_bot_guilds(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """List all guilds the bot is currently in."""
    result = await vk.send_bot_command("list_guilds", {})
    if result is None:
        raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return BotGuildListResponse(guilds=[BotGuildInfo(**g) for g in result.get("guilds", [])])
