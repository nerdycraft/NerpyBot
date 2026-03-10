"""WoW Blizzard API proxy routes — realm search and guild validation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from web.cache import ValkeyClient
from web.dependencies import get_current_user, get_valkey

router = APIRouter(prefix="/wow", tags=["wow"])


async def send_bot_command_sync(vk: ValkeyClient, command: str, payload: dict) -> dict | None:
    """Thin async wrapper — exists so tests can patch it cleanly."""
    return await vk.send_bot_command(command, payload, timeout=5.0)


@router.get("/realms")
async def search_realms(
    region: str = Query(..., pattern="^(eu|us)$"),
    q: str = Query(..., min_length=2),
    _user: dict = Depends(get_current_user),
    vk: ValkeyClient = Depends(get_valkey),
) -> list[dict]:
    """Search WoW realms by name for a given region. Returns 503 if bot is offline."""
    result = await send_bot_command_sync(vk, "search_realms", {"region": region, "q": q})
    if result is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot offline")
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result["error"])
    return result.get("realms", [])


@router.get("/guilds/validate")
async def validate_wow_guild(
    region: str = Query(..., pattern="^(eu|us)$"),
    realm: str = Query(..., min_length=1),
    name: str = Query(..., min_length=1),
    _user: dict = Depends(get_current_user),
    vk: ValkeyClient = Depends(get_valkey),
) -> dict:
    """Check whether a WoW guild exists on the given realm. Returns 503 if bot is offline."""
    result = await send_bot_command_sync(
        vk, "validate_wow_guild", {"region": region, "realm_slug": realm, "guild_name": name}
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot offline")
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result["error"])
    return {"valid": result.get("valid", False), "display_name": result.get("display_name")}
