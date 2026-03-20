"""SSE streaming endpoints for live status updates."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from web.cache import ValkeyClient
from web.dependencies import get_valkey, require_operator

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/operator", tags=["sse"])

_active_connections: dict[str, int] = {}
_MAX_SSE_PER_USER = 3
_HEALTH_POLL_INTERVAL = 10  # seconds
_HEARTBEAT_INTERVAL = 30  # seconds


@router.get("/health/live")
async def health_live(
    request: Request,
    user: dict = Depends(require_operator),
    vk: ValkeyClient = Depends(get_valkey),
) -> EventSourceResponse:
    """SSE stream of live health metrics from the bot."""
    user_id = user["sub"]
    count = _active_connections.get(user_id, 0)
    if count >= _MAX_SSE_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many SSE connections",
        )
    # Increment before yielding control to the event loop so concurrent requests
    # from the same user see the updated count immediately (no TOCTOU gap).
    _active_connections[user_id] = count + 1
    return EventSourceResponse(
        _health_event_generator(user_id, vk, request),
        media_type="text/event-stream",
    )


async def _health_event_generator(
    user_id: str,
    vk: ValkeyClient,
    request: Request,
) -> AsyncGenerator[dict, None]:
    """Poll the bot for health metrics and yield as SSE events."""
    last_heartbeat = time.monotonic()

    try:
        while True:
            if await request.is_disconnected():
                break

            result = await vk.send_bot_command("health_live", {}, timeout=5.0)
            # Re-check after the potentially slow Valkey call — skip yield if already gone.
            if await request.is_disconnected():
                break
            if result and "error" not in result:
                yield {"event": "health", "data": json.dumps(result)}

            # Heartbeat fires every _HEARTBEAT_INTERVAL regardless of data events
            # so proxies and browsers can detect a dead connection.
            if time.monotonic() - last_heartbeat >= _HEARTBEAT_INTERVAL:
                yield {"comment": "heartbeat"}
                last_heartbeat = time.monotonic()

            await asyncio.sleep(_HEALTH_POLL_INTERVAL)

    except asyncio.CancelledError:
        pass
    except Exception:
        _log.debug("SSE health generator error for user %s", user_id, exc_info=True)
    finally:
        remaining = _active_connections.get(user_id, 0) - 1
        if remaining <= 0:
            _active_connections.pop(user_id, None)
        else:
            _active_connections[user_id] = remaining
