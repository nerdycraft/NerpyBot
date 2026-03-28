"""Tests for guild Twitch notification CRUD endpoints."""

from unittest.mock import AsyncMock

import pytest

from tests.web.conftest import make_auth_header

GUILD_ID = 987654321


@pytest.fixture(autouse=True)
def seed_permissions(fake_valkey):
    fake_valkey.set_permissions("123456", {str(GUILD_ID): {"level": "admin", "name": "Test", "icon": None}}, ttl=300)


@pytest.fixture(autouse=True)
def seed_premium_user(web_db_session):
    from models.admin import PremiumUser

    PremiumUser.grant(123456, 111222333, web_db_session)
    web_db_session.commit()


@pytest.fixture
def twitch_client(web_db_engine, fake_valkey):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from web.app import create_app
    from web.config import WebConfig
    from web.dependencies import get_db_session

    cfg = WebConfig(
        client_id="x",
        client_secret="x",
        redirect_uri="x",
        jwt_secret="test_jwt_secret",
        jwt_expiry_hours=1,
        valkey_url="x",
        ops=[111222333],
        db_connection_string="sqlite:///:memory:",
        twitch_client_id="t_id",
        twitch_client_secret="t_sec",
        twitch_webhook_url="https://example.com/webhooks/twitch",
        twitch_webhook_secret="t_wh_sec",
    )
    app = create_app(cfg, fake_valkey)
    sf = sessionmaker(bind=web_db_engine, expire_on_commit=False)

    def override():
        s = sf()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = override
    with TestClient(app) as tc:
        yield tc


@pytest.fixture
def auth_header():
    return make_auth_header()


class TestListTwitchNotifications:
    def test_empty_list(self, twitch_client, auth_header):
        resp = twitch_client.get(f"/api/guilds/{GUILD_ID}/twitch-notifications", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json() == []


class TestCreateTwitchNotification:
    def test_creates_notification(self, twitch_client, auth_header):
        mock_users = [{"id": "12345", "login": "shroud", "display_name": "shroud"}]
        twitch_client.app.state.twitch_client.get_users = AsyncMock(return_value=mock_users)
        resp = twitch_client.post(
            f"/api/guilds/{GUILD_ID}/twitch-notifications",
            json={"channel_id": 111222333, "streamer": "shroud"},
            headers=auth_header,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["streamer"] == "shroud"
        assert data["channel_id"] == "111222333"

    def test_422_on_unknown_twitch_user(self, twitch_client, auth_header):
        twitch_client.app.state.twitch_client.get_users = AsyncMock(return_value=[])
        resp = twitch_client.post(
            f"/api/guilds/{GUILD_ID}/twitch-notifications",
            json={"channel_id": 111, "streamer": "doesnotexist"},
            headers=auth_header,
        )
        assert resp.status_code == 422

    def test_409_on_duplicate(self, twitch_client, auth_header, web_db_session):
        from models.twitch import TwitchNotifications

        web_db_session.add(
            TwitchNotifications(GuildId=GUILD_ID, ChannelId=111222333, Streamer="shroud", StreamerDisplayName="shroud")
        )
        web_db_session.commit()

        mock_users = [{"id": "12345", "login": "shroud", "display_name": "shroud"}]
        twitch_client.app.state.twitch_client.get_users = AsyncMock(return_value=mock_users)
        resp = twitch_client.post(
            f"/api/guilds/{GUILD_ID}/twitch-notifications",
            json={"channel_id": 111222333, "streamer": "shroud"},
            headers=auth_header,
        )
        assert resp.status_code == 409


class TestUpdateTwitchNotification:
    def test_patch_message(self, twitch_client, auth_header, web_db_session):
        from models.twitch import TwitchNotifications

        row = TwitchNotifications(GuildId=GUILD_ID, ChannelId=111, Streamer="shroud", StreamerDisplayName="shroud")
        web_db_session.add(row)
        web_db_session.commit()

        resp = twitch_client.patch(
            f"/api/guilds/{GUILD_ID}/twitch-notifications/{row.Id}",
            json={"message": "Shroud is live!"},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Shroud is live!"

    def test_patch_404_wrong_guild(self, twitch_client, auth_header, web_db_session):
        from models.twitch import TwitchNotifications

        row = TwitchNotifications(GuildId=99999, ChannelId=111, Streamer="shroud", StreamerDisplayName="shroud")
        web_db_session.add(row)
        web_db_session.commit()

        resp = twitch_client.patch(
            f"/api/guilds/{GUILD_ID}/twitch-notifications/{row.Id}",
            json={"message": "hi"},
            headers=auth_header,
        )
        assert resp.status_code == 404


class TestDeleteTwitchNotification:
    def test_delete_returns_204(self, twitch_client, auth_header, web_db_session):
        from models.twitch import TwitchNotifications

        row = TwitchNotifications(GuildId=GUILD_ID, ChannelId=111, Streamer="shroud", StreamerDisplayName="shroud")
        web_db_session.add(row)
        web_db_session.commit()

        resp = twitch_client.delete(
            f"/api/guilds/{GUILD_ID}/twitch-notifications/{row.Id}",
            headers=auth_header,
        )
        assert resp.status_code == 204

    def test_delete_404_wrong_guild(self, twitch_client, auth_header, web_db_session):
        from models.twitch import TwitchNotifications

        row = TwitchNotifications(GuildId=99999, ChannelId=111, Streamer="shroud", StreamerDisplayName="shroud")
        web_db_session.add(row)
        web_db_session.commit()

        resp = twitch_client.delete(
            f"/api/guilds/{GUILD_ID}/twitch-notifications/{row.Id}",
            headers=auth_header,
        )
        assert resp.status_code == 404
