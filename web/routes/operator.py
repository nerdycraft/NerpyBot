"""Operator routes — health, module management."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web.dependencies import get_valkey, require_operator
from web.schemas import HealthResponse, ModuleActionResponse
from web.valkey import ValkeyClient

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
    return HealthResponse(status="online", **result)


@router.get("/modules")
async def list_modules(
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Request loaded modules from the bot."""
    result = await vk.send_bot_command("list_modules", {})
    if result is None:
        return {"modules": [], "status": "bot unreachable"}
    return result


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
