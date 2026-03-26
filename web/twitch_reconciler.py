"""Twitch EventSub reconciliation -- keeps DB config in sync with Twitch-side subscriptions."""

from __future__ import annotations

import logging

_log = logging.getLogger(__name__)


async def reconcile_once(app_state) -> None:
    """Run one reconciliation cycle. Called by BackgroundTasks after POST/DELETE."""
    # Full implementation in Task 8; stub ensures routes can import this.
    pass


async def reconciler_loop(app_state) -> None:
    """Background loop that reconciles every 5 minutes. Started in app lifespan."""
    pass
