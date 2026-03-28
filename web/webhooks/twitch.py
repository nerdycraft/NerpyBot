"""Twitch EventSub webhook receiver."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from models.twitch import SUB_STATUS_REVOKED, TwitchEventSubSubscription
from web.cache import ValkeyClient
from web.dependencies import get_db_session, get_valkey
from web.twitch import TwitchClient

_log = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

_MAX_AGE_SECONDS = 10 * 60  # 10 minutes — replay protection window


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse RFC3339 timestamp from Twitch header. Returns None on parse failure."""
    try:
        normalized = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.astimezone(UTC)
    except (ValueError, AttributeError):
        return None


@router.post("/webhooks/twitch", include_in_schema=False)
async def twitch_webhook(
    request: Request,
    session: Session = Depends(get_db_session),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Receive and dispatch Twitch EventSub webhook messages."""
    config = request.app.state.config

    if not config.twitch_client_id:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Twitch integration not configured")

    body = await request.body()

    msg_id = request.headers.get("Twitch-Eventsub-Message-Id", "")
    timestamp = request.headers.get("Twitch-Eventsub-Message-Timestamp", "")
    signature = request.headers.get("Twitch-Eventsub-Message-Signature", "")
    msg_type = request.headers.get("Twitch-Eventsub-Message-Type", "")

    if not TwitchClient.verify_signature(config.twitch_webhook_secret, msg_id, timestamp, body, signature):
        _log.warning("twitch_webhook: invalid HMAC signature for msg_id=%s", msg_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    msg_time = _parse_timestamp(timestamp)
    if msg_time is None or abs((datetime.now(UTC) - msg_time).total_seconds()) > _MAX_AGE_SECONDS:
        _log.warning("twitch_webhook: stale or unparseable timestamp=%s", timestamp)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Message too old")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    if msg_type == "webhook_callback_verification":
        challenge = payload.get("challenge", "")
        return Response(content=challenge, media_type="text/plain")

    if msg_type == "notification":
        if not vk.claim_twitch_event(msg_id, ttl=_MAX_AGE_SECONDS + 60):
            _log.debug("twitch_webhook: duplicate msg_id=%s — skipping", msg_id)
            return Response(status_code=204)

        sub = payload.get("subscription", {})
        event = payload.get("event", {})
        event_type = sub.get("type", "")
        try:
            vk.notify_bot(
                "twitch_event",
                {
                    "event_type": event_type,
                    "broadcaster_login": event.get("broadcaster_user_login", ""),
                    "broadcaster_name": event.get("broadcaster_user_name", ""),
                    "started_at": event.get("started_at", ""),
                },
            )
        except Exception:
            _log.exception("twitch_webhook: failed to publish event msg_id=%s — releasing claim", msg_id)
            vk.delete_twitch_event_claim(msg_id)
            raise
        return Response(status_code=204)

    if msg_type == "revocation":
        sub = payload.get("subscription", {})
        sub_id = sub.get("id", "")
        if sub_id:
            row = TwitchEventSubSubscription.get_by_twitch_id(sub_id, session)
            if row:
                row.Status = SUB_STATUS_REVOKED
                session.commit()
        return Response(status_code=204)

    # Unknown message type — accept and ignore
    return Response(status_code=204)
