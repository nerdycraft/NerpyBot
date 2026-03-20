"""Operator routes — health, module management."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from fastapi import APIRouter, Depends

from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from web.dependencies import get_db_session, get_valkey, invalidate_premium_cache, require_operator
from web.schemas import (
    BotGuildInfo,
    BotGuildListResponse,
    BotPermissionGuildResult,
    BotPermissionSubscription,
    BotPermissionsResponse,
    DebugToggleResponse,
    ErrorActionResponse,
    ErrorStatusBucket,
    ErrorStatusResponse,
    ErrorSuppressRequest,
    HealthResponse,
    ModuleActionResponse,
    ModuleListResponse,
    PremiumUserGrant,
    PremiumUserSchema,
    RecipeCacheBrowseResponse,
    RecipeCacheEntry,
    RecipeCacheProfession,
    RecipeSyncResponse,
    RecipeSyncStatusResponse,
    SyncCommandsRequest,
    SyncCommandsResponse,
    VoiceConnectionDetail,
)
from web.cache import ValkeyClient

log = logging.getLogger("nerpybot")


def _parse_voice_details(raw: list) -> list[VoiceConnectionDetail]:
    result = []
    for d in raw:
        if not isinstance(d, dict):
            log.warning("health: unexpected voice_details entry type %s, skipping", type(d).__name__)
            continue
        try:
            result.append(VoiceConnectionDetail(**d))
        except (ValidationError, TypeError) as exc:
            log.warning("health: malformed voice_details entry %r: %s", d, exc)
    return result


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
    invalidate_premium_cache()
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
    invalidate_premium_cache()


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
        voice_details=_parse_voice_details(result.get("voice_details", [])),
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
    return ModuleListResponse(modules=result.get("modules", []), available=result.get("available", []))


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


async def _fetch_guild_list(vk: ValkeyClient) -> list[dict]:
    result = await vk.send_bot_command("list_guilds", {})
    if result is None:
        raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return result.get("guilds", [])


@router.get("/guilds", response_model=BotGuildListResponse)
async def list_bot_guilds(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """List all guilds the bot is currently in."""
    return BotGuildListResponse(guilds=[BotGuildInfo(**g) for g in await _fetch_guild_list(vk)])


@router.get("/guilds/{guild_id}", response_model=BotGuildInfo)
async def get_bot_guild(
    guild_id: str,
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Get info for a single guild the bot is in."""
    for g in await _fetch_guild_list(vk):
        if g.get("id") == guild_id:
            return BotGuildInfo(**g)
    raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Guild not found")


# ── Recipe sync ──


@router.post("/recipe-sync", response_model=RecipeSyncResponse)
async def trigger_recipe_sync(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Fire-and-forget recipe sync via the bot's Blizzard API connection."""
    result = await vk.send_bot_command("recipe_sync", {})
    if result is None:
        return RecipeSyncResponse(queued=False, error="Bot unreachable")
    return RecipeSyncResponse(**result)


@router.get("/recipe-sync/status", response_model=RecipeSyncStatusResponse)
async def get_recipe_sync_status(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Return current recipe cache counts per type."""
    result = await vk.send_bot_command("recipe_sync_status", {})
    if result is None:
        raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return RecipeSyncStatusResponse(counts=result.get("counts", {}))


@router.get("/recipe-cache", response_model=RecipeCacheBrowseResponse)
async def browse_recipe_cache(
    recipe_type: str | None = None,
    profession_id: int | None = None,
    expansion: str | None = None,
    offset: int = 0,
    limit: int = 50,
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """Browse cached recipes with optional filters. Returns up to `limit` rows."""
    from models.wow import CraftingRecipeCache
    from sqlalchemy import asc, func

    q = session.query(CraftingRecipeCache)
    if recipe_type:
        q = q.filter(CraftingRecipeCache.RecipeType == recipe_type)
    if profession_id is not None:
        q = q.filter(CraftingRecipeCache.ProfessionId == profession_id)
    if expansion:
        q = q.filter(CraftingRecipeCache.ExpansionName == expansion)

    total = q.with_entities(func.count(CraftingRecipeCache.RecipeId)).scalar() or 0
    rows = q.order_by(asc(CraftingRecipeCache.ItemName)).offset(offset).limit(limit).all()

    # Dropdown option lists are only needed on the first page (filter change / initial load).
    # On subsequent pages the frontend keeps the cached values from the first response.
    professions: list[RecipeCacheProfession] = []
    expansions: list[str] = []
    if offset == 0:
        type_filter = CraftingRecipeCache.RecipeType == recipe_type if recipe_type else True
        prof_rows = (
            session.query(CraftingRecipeCache.ProfessionId, CraftingRecipeCache.ProfessionName)
            .filter(type_filter)
            .distinct()
            .order_by(asc(CraftingRecipeCache.ProfessionName))
            .all()
        )
        exp_rows = (
            session.query(CraftingRecipeCache.ExpansionName)
            .filter(type_filter)
            .filter(CraftingRecipeCache.ExpansionName.isnot(None))
            .distinct()
            .order_by(asc(CraftingRecipeCache.ExpansionName))
            .all()
        )
        professions = [RecipeCacheProfession(id=p[0], name=p[1]) for p in prof_rows]
        expansions = [e[0] for e in exp_rows]

    return RecipeCacheBrowseResponse(
        recipes=[
            RecipeCacheEntry(
                recipe_id=r.RecipeId,
                item_name=r.ItemName,
                profession_id=r.ProfessionId,
                profession_name=r.ProfessionName,
                recipe_type=r.RecipeType,
                item_class_name=r.ItemClassName,
                item_subclass_name=r.ItemSubClassName,
                expansion_name=r.ExpansionName,
                category_name=r.CategoryName,
                wowhead_url=r.wowhead_url,
            )
            for r in rows
        ],
        professions=professions,
        expansions=expansions,
        total=total,
    )


# ── Bot permissions ──


@router.get("/bot-permissions", response_model=BotPermissionsResponse)
async def get_bot_permissions(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Check bot permissions across all guilds."""
    result = await vk.send_bot_command("bot_permissions", {})
    if result is None:
        raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return BotPermissionsResponse(guilds=[BotPermissionGuildResult(**g) for g in result.get("guilds", [])])


@router.get("/bot-permissions/subscriptions", response_model=list[BotPermissionSubscription])
async def list_permission_subscriptions(
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """Return which guilds the current operator is subscribed to for missing-permission DMs."""
    from models.admin import PermissionSubscriber

    user_id = int(user["sub"])
    rows = session.query(PermissionSubscriber).filter(PermissionSubscriber.UserId == user_id).all()
    return [BotPermissionSubscription(guild_id=str(r.GuildId), subscribed=True) for r in rows]


@router.post("/bot-permissions/subscriptions/{guild_id}", response_model=BotPermissionSubscription)
async def subscribe_bot_permissions(
    guild_id: str,
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """Subscribe to missing-permission DMs for a guild."""
    from models.admin import PermissionSubscriber

    user_id = int(user["sub"])
    try:
        gid = int(guild_id)
    except ValueError:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid guild_id")
    existing = PermissionSubscriber.get(gid, user_id, session)
    if existing is None:
        session.add(PermissionSubscriber(GuildId=gid, UserId=user_id))
    return BotPermissionSubscription(guild_id=guild_id, subscribed=True)


@router.delete("/bot-permissions/subscriptions/{guild_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def unsubscribe_bot_permissions(
    guild_id: str,
    user: dict = Depends(require_operator),
    session: Session = Depends(get_db_session),
):
    """Unsubscribe from missing-permission DMs for a guild."""
    from models.admin import PermissionSubscriber

    user_id = int(user["sub"])
    try:
        gid = int(guild_id)
    except ValueError:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid guild_id")
    PermissionSubscriber.delete(gid, user_id, session)


# ── Error control ──


@router.get("/error-status", response_model=ErrorStatusResponse)
async def get_error_status(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Return current error throttle and suppression state."""
    result = await vk.send_bot_command("error_status", {})
    if result is None:
        raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return ErrorStatusResponse(
        is_suppressed=result.get("is_suppressed", False),
        suppressed_remaining=result.get("suppressed_remaining"),
        throttle_window=result.get("throttle_window", 900),
        buckets={k: ErrorStatusBucket(**v) for k, v in result.get("buckets", {}).items()},
        debug_enabled=result.get("debug_enabled"),
    )


@router.post("/error-suppress", response_model=ErrorActionResponse)
async def suppress_errors(
    body: ErrorSuppressRequest,
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Suppress error DM notifications for a duration."""
    result = await vk.send_bot_command("error_suppress", {"duration": body.duration})
    if result is None:
        return ErrorActionResponse(success=False, error="Bot unreachable")
    return ErrorActionResponse(**result)


@router.post("/error-resume", response_model=ErrorActionResponse)
async def resume_errors(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Resume error DM notifications."""
    result = await vk.send_bot_command("error_resume", {})
    if result is None:
        return ErrorActionResponse(success=False, error="Bot unreachable")
    return ErrorActionResponse(**result)


# ── Debug toggle ──


@router.post("/debug-toggle", response_model=DebugToggleResponse)
async def toggle_debug(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Toggle debug logging on the bot at runtime."""
    result = await vk.send_bot_command("debug_toggle", {})
    if result is None:
        raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return DebugToggleResponse(debug_enabled=result.get("debug_enabled", False))


# ── Command sync ──


@router.post("/sync-commands", response_model=SyncCommandsResponse)
async def sync_commands(
    body: SyncCommandsRequest,
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Sync Discord slash commands via the bot."""
    result = await vk.send_bot_command("sync_commands", {"mode": body.mode, "guild_ids": body.guild_ids})
    if result is None:
        return SyncCommandsResponse(success=False, error="Bot unreachable")
    return SyncCommandsResponse(**result)
