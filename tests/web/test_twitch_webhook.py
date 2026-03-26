"""Tests for the Twitch EventSub webhook receiver."""

import hashlib
import hmac
import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

WEBHOOK_SECRET = "test_webhook_secret"


def _make_sig(secret: str, msg_id: str, timestamp: str, body: bytes) -> str:
    raw = (msg_id + timestamp).encode() + body
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _ts_now() -> str:
    """ISO timestamp within the 10-minute window."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def twitch_client(web_db_engine, web_config, fake_valkey):
    from sqlalchemy.orm import sessionmaker

    from web.app import create_app
    from web.config import WebConfig
    from web.dependencies import get_db_session

    cfg = WebConfig(
        client_id=web_config.client_id,
        client_secret=web_config.client_secret,
        redirect_uri=web_config.redirect_uri,
        jwt_secret=web_config.jwt_secret,
        jwt_expiry_hours=web_config.jwt_expiry_hours,
        valkey_url=web_config.valkey_url,
        ops=web_config.ops,
        db_connection_string=web_config.db_connection_string,
        twitch_client_id="t_id",
        twitch_client_secret="t_sec",
        twitch_webhook_url="https://example.com/webhooks/twitch",
        twitch_webhook_secret=WEBHOOK_SECRET,
    )
    app = create_app(cfg, fake_valkey)
    test_session_factory = sessionmaker(bind=web_db_engine, expire_on_commit=False)

    def override_session():
        session = test_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_session
    with TestClient(app) as tc:
        yield tc


def _post_webhook(client, msg_type: str, body_dict: dict, msg_id: str = "msg-001", secret: str = WEBHOOK_SECRET):
    body = json.dumps(body_dict).encode()
    ts = _ts_now()
    sig = _make_sig(secret, msg_id, ts, body)
    return client.post(
        "/webhooks/twitch",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Twitch-Eventsub-Message-Id": msg_id,
            "Twitch-Eventsub-Message-Timestamp": ts,
            "Twitch-Eventsub-Message-Signature": sig,
            "Twitch-Eventsub-Message-Type": msg_type,
        },
    )


class TestWebhookChallenge:
    def test_returns_challenge_as_plain_text(self, twitch_client):
        body = {"challenge": "mychallengetoken", "subscription": {"type": "stream.online"}}
        resp = _post_webhook(twitch_client, "webhook_callback_verification", body)
        assert resp.status_code == 200
        assert resp.text == "mychallengetoken"
        assert "text/plain" in resp.headers["content-type"]

    def test_rejects_invalid_signature(self, twitch_client):
        body = {"challenge": "abc"}
        resp = _post_webhook(twitch_client, "webhook_callback_verification", body, secret="wrongsecret")
        assert resp.status_code == 403


class TestWebhookNotification:
    def test_valid_notification_returns_204(self, twitch_client, fake_valkey):
        body = {
            "subscription": {"type": "stream.online"},
            "event": {
                "broadcaster_user_login": "shroud",
                "broadcaster_user_name": "shroud",
                "started_at": "2024-01-01T00:00:00Z",
            },
        }
        from unittest.mock import patch

        published = []
        with patch.object(fake_valkey._client, "publish", side_effect=lambda ch, msg: published.append(msg)):
            resp = _post_webhook(twitch_client, "notification", body)
        assert resp.status_code == 204
        assert any("twitch_event" in m for m in published)

    def test_duplicate_notification_returns_204_without_publish(self, twitch_client, fake_valkey):
        body = {
            "subscription": {"type": "stream.online"},
            "event": {"broadcaster_user_login": "shroud", "broadcaster_user_name": "shroud", "started_at": "x"},
        }
        from unittest.mock import patch

        published = []
        with patch.object(fake_valkey._client, "publish", side_effect=lambda ch, msg: published.append(msg)):
            _post_webhook(twitch_client, "notification", body, msg_id="dup-id")
            resp = _post_webhook(twitch_client, "notification", body, msg_id="dup-id")
        assert resp.status_code == 204
        assert len(published) == 1  # only first was published

    def test_stale_timestamp_returns_403(self, twitch_client):
        old_ts = "2020-01-01T00:00:00Z"
        body_bytes = json.dumps({"subscription": {"type": "stream.online"}, "event": {}}).encode()
        sig = _make_sig(WEBHOOK_SECRET, "msg-stale", old_ts, body_bytes)
        resp = twitch_client.post(
            "/webhooks/twitch",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "Twitch-Eventsub-Message-Id": "msg-stale",
                "Twitch-Eventsub-Message-Timestamp": old_ts,
                "Twitch-Eventsub-Message-Signature": sig,
                "Twitch-Eventsub-Message-Type": "notification",
            },
        )
        assert resp.status_code == 403


class TestWebhookRevocation:
    def test_revocation_returns_204(self, twitch_client, web_db_session):
        from datetime import UTC, datetime
        from models.twitch import TwitchEventSubSubscription

        sub = TwitchEventSubSubscription(
            TwitchSubscriptionId="sub-abc",
            StreamerLogin="shroud",
            StreamerUserId="123",
            EventType="stream.online",
            Status="enabled",
            CreatedAt=datetime.now(UTC),
        )
        web_db_session.add(sub)
        web_db_session.commit()

        body = {"subscription": {"id": "sub-abc", "type": "stream.online", "status": "authorization_revoked"}}
        resp = _post_webhook(twitch_client, "revocation", body, msg_id="rev-001")
        assert resp.status_code == 204

        # Verify the DB row was actually revoked
        web_db_session.expire_all()
        updated = TwitchEventSubSubscription.get_by_twitch_id("sub-abc", web_db_session)
        assert updated is not None
        assert updated.Status == "revoked"


class TestWebhookDisabled:
    def test_returns_503_when_no_client_id(self, web_config, fake_valkey):
        """When twitch_client_id is empty, the endpoint returns 503."""
        from web.app import create_app

        app = create_app(web_config, fake_valkey)  # web_config has no twitch config
        with TestClient(app) as tc:
            resp = tc.post("/webhooks/twitch", content=b"{}", headers={"Content-Type": "application/json"})
        assert resp.status_code == 503
