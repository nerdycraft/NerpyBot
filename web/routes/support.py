"""Support message routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from web.cache import ValkeyClient
from web.dependencies import get_current_user, get_valkey
from web.schemas import SupportMessageRequest, SupportMessageResponse

router = APIRouter(prefix="/support", tags=["support"])


@router.post("/message", response_model=SupportMessageResponse)
async def send_support_message(
    body: SupportMessageRequest,
    user: dict = Depends(get_current_user),
    vk: ValkeyClient = Depends(get_valkey),
) -> SupportMessageResponse:
    """Send a support message (bug report, feature request, or feedback) to bot operators via DM."""
    result = await vk.send_bot_command(
        "support_message",
        {
            "user_id": user["sub"],
            "username": user.get("username", "unknown"),
            "category": body.category,
            "message": body.message,
        },
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bot unreachable")
    return SupportMessageResponse(**result)
