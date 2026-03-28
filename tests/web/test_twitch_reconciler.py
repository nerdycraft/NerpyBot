"""Unit tests for the Twitch EventSub reconciler."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from utils.database import BASE


@pytest.fixture
def reconciler_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from models.twitch import TwitchEventSubSubscription, TwitchNotifications  # noqa: F401

    BASE.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class TestReconcileOnce:
    async def test_creates_missing_subscription(self, reconciler_db):
        session = reconciler_db()
        from models.twitch import TwitchNotifications

        session.add(TwitchNotifications(GuildId=111, ChannelId=222, Streamer="shroud", StreamerDisplayName="shroud"))
        session.commit()
        session.close()

        mock_twitch = AsyncMock()
        mock_twitch.get_users.return_value = [{"id": "12345", "login": "shroud", "display_name": "shroud"}]
        mock_twitch.create_eventsub_subscription.return_value = {
            "id": "sub-xyz",
            "status": "webhook_callback_verification_pending",
        }

        mock_state = MagicMock()
        mock_state.session_factory = reconciler_db
        mock_state.twitch_client = mock_twitch
        mock_state.config.twitch_webhook_url = "https://example.com/webhooks/twitch"
        mock_state.config.twitch_webhook_secret = "secret"

        from web.twitch_reconciler import reconcile_once

        await reconcile_once(mock_state)

        mock_twitch.create_eventsub_subscription.assert_called_once_with(
            "stream.online", "12345", "https://example.com/webhooks/twitch", "secret"
        )

    async def test_deletes_orphaned_subscription(self, reconciler_db):
        session = reconciler_db()
        from models.twitch import TwitchEventSubSubscription

        session.add(
            TwitchEventSubSubscription(
                TwitchSubscriptionId="sub-orphan",
                StreamerLogin="xqc",
                StreamerUserId="99",
                EventType="stream.online",
                Status="enabled",
                CreatedAt=datetime.now(UTC),
            )
        )
        session.commit()
        session.close()

        mock_twitch = AsyncMock()
        mock_state = MagicMock()
        mock_state.session_factory = reconciler_db
        mock_state.twitch_client = mock_twitch
        mock_state.config.twitch_webhook_url = "https://example.com/webhooks/twitch"
        mock_state.config.twitch_webhook_secret = "secret"

        from web.twitch_reconciler import reconcile_once

        await reconcile_once(mock_state)

        mock_twitch.delete_eventsub_subscription.assert_called_once_with("sub-orphan")

    async def test_creates_offline_subscription_when_notify_offline(self, reconciler_db):
        """When any config has NotifyOffline=True, stream.offline sub is also created."""
        session = reconciler_db()
        from models.twitch import TwitchNotifications

        session.add(
            TwitchNotifications(
                GuildId=111,
                ChannelId=222,
                Streamer="shroud",
                StreamerDisplayName="shroud",
                NotifyOffline=True,
            )
        )
        session.commit()
        session.close()

        mock_twitch = AsyncMock()
        mock_twitch.get_users.return_value = [{"id": "12345", "login": "shroud", "display_name": "shroud"}]
        mock_twitch.create_eventsub_subscription.return_value = {"id": "sub-xyz"}

        mock_state = MagicMock()
        mock_state.session_factory = reconciler_db
        mock_state.twitch_client = mock_twitch
        mock_state.config.twitch_webhook_url = "https://example.com/webhooks/twitch"
        mock_state.config.twitch_webhook_secret = "secret"

        from web.twitch_reconciler import reconcile_once

        await reconcile_once(mock_state)

        calls = mock_twitch.create_eventsub_subscription.call_args_list
        event_types = [c.args[0] for c in calls]
        assert "stream.online" in event_types
        assert "stream.offline" in event_types

    async def test_skips_when_no_client(self, reconciler_db):
        mock_state = MagicMock()
        mock_state.session_factory = reconciler_db
        mock_state.twitch_client = None

        from web.twitch_reconciler import reconcile_once

        await reconcile_once(mock_state)  # should not raise
