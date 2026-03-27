"""Twitch EventSub reconciliation -- keeps DB config in sync with Twitch-side subscriptions."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from models.twitch import STREAM_OFFLINE, STREAM_ONLINE, SUB_STATUS_ENABLED, SUB_STATUS_PENDING

_log = logging.getLogger(__name__)

_RECONCILE_INTERVAL = 5 * 60  # 5 minutes


async def reconcile_once(app_state) -> None:
    """Run one reconciliation cycle. Called directly or from the background loop."""
    twitch_client = getattr(app_state, "twitch_client", None)
    if twitch_client is None:
        return

    session_factory = app_state.session_factory
    config = app_state.config

    session = session_factory()
    try:
        await _run_cycle(session, twitch_client, config)
    except Exception:
        _log.exception("twitch reconciler: unhandled error in reconcile_once")
    finally:
        session.close()


def _needs_heal(streamer: str, existing_by_key: dict, offline_needed: set[str]) -> bool:
    """Return True if this streamer needs any EventSub subscription created or healed."""
    # Always check stream.online
    if (streamer, STREAM_ONLINE) not in existing_by_key:
        return True
    if existing_by_key[(streamer, STREAM_ONLINE)].Status not in (SUB_STATUS_ENABLED, SUB_STATUS_PENDING):
        return True
    # Check stream.offline if any config needs it
    if streamer in offline_needed:
        key = (streamer, STREAM_OFFLINE)
        if key not in existing_by_key or existing_by_key[key].Status not in (SUB_STATUS_ENABLED, SUB_STATUS_PENDING):
            return True
    return False


async def _run_cycle(session, twitch_client, config) -> None:
    from models.twitch import TwitchEventSubSubscription, TwitchNotifications

    # Desired: distinct streamers in notification config
    desired_streamers = set(TwitchNotifications.get_all_distinct_streamers(session))
    offline_needed = set(TwitchNotifications.get_streamers_needing_offline(session))

    # Actual: all EventSub subscriptions in DB
    existing_subs = TwitchEventSubSubscription.get_all(session)
    existing_by_key: dict[tuple[str, str], TwitchEventSubSubscription] = {
        (s.StreamerLogin, s.EventType): s for s in existing_subs
    }

    # Resolve user IDs for missing/broken streamers
    missing_streamers = {s for s in desired_streamers if _needs_heal(s, existing_by_key, offline_needed)}
    user_map: dict[str, dict] = {}
    if missing_streamers:
        try:
            users = await twitch_client.get_users(list(missing_streamers))
            user_map = {u["login"].lower(): u for u in users}
        except Exception:
            _log.exception("twitch reconciler: failed to resolve user IDs")

    # Create missing subscriptions
    for streamer in missing_streamers:
        user_info = user_map.get(streamer)
        if not user_info:
            _log.warning("twitch reconciler: Twitch user not found for '%s' -- skipping", streamer)
            continue
        broadcaster_id = user_info["id"]

        needs_offline = streamer in offline_needed
        event_types = [STREAM_ONLINE]
        if needs_offline:
            event_types.append(STREAM_OFFLINE)

        for event_type in event_types:
            key = (streamer, event_type)
            existing = existing_by_key.get(key)
            if existing and existing.Status in (SUB_STATUS_ENABLED, SUB_STATUS_PENDING):
                continue
            try:
                sub = await twitch_client.create_eventsub_subscription(
                    event_type,
                    broadcaster_id,
                    config.twitch_webhook_url,
                    config.twitch_webhook_secret,
                )
                sub_id = sub.get("id", "")
                if not sub_id:
                    continue
                if existing:
                    existing.TwitchSubscriptionId = sub_id
                    existing.Status = SUB_STATUS_PENDING
                else:
                    row = TwitchEventSubSubscription(
                        TwitchSubscriptionId=sub_id,
                        StreamerLogin=streamer,
                        StreamerUserId=broadcaster_id,
                        EventType=event_type,
                        Status=SUB_STATUS_PENDING,
                        CreatedAt=datetime.now(UTC),
                    )
                    session.add(row)
                session.commit()
                _log.info(
                    "twitch reconciler: created %s subscription for '%s' (sub_id=%s)",
                    event_type,
                    streamer,
                    sub_id,
                )
            except Exception:
                _log.exception("twitch reconciler: failed to create %s for '%s'", event_type, streamer)

    # Delete orphaned subscriptions (streamer no longer in desired set)
    for (streamer, event_type), sub in existing_by_key.items():
        if streamer not in desired_streamers:
            try:
                await twitch_client.delete_eventsub_subscription(sub.TwitchSubscriptionId)
                session.delete(sub)
                session.commit()
                _log.info("twitch reconciler: deleted orphaned %s for '%s'", event_type, streamer)
            except Exception:
                _log.exception("twitch reconciler: failed to delete orphaned sub for '%s'", streamer)


async def reconciler_loop(app_state) -> None:
    """Background loop that reconciles every 5 minutes. Started in app lifespan."""
    try:
        while True:
            await asyncio.sleep(_RECONCILE_INTERVAL)
            await reconcile_once(app_state)
    except asyncio.CancelledError:
        pass
    except Exception:
        _log.exception("twitch reconciler: background loop crashed")
