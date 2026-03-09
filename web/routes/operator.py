"""Operator routes — health, module management."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web.dependencies import get_valkey, require_operator
from web.schemas import HealthResponse, ModuleActionResponse, ModuleListResponse
from web.cache import ValkeyClient

router = APIRouter(prefix="/operator", tags=["operator"])


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
        python_version=result.get("python_version"),
        discord_py_version=result.get("discord_py_version"),
        bot_version=result.get("bot_version"),
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
