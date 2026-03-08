from unittest.mock import patch


from tests.web.conftest import make_auth_header


class TestAuthLogin:
    def test_login_redirects_to_discord(self, client):
        response = client.get("/api/auth/login", follow_redirects=False)
        assert response.status_code == 307
        assert "discord.com/oauth2/authorize" in response.headers["location"]
        assert "identify" in response.headers["location"]
        assert "guilds" in response.headers["location"]

    def test_login_includes_client_id(self, client):
        response = client.get("/api/auth/login", follow_redirects=False)
        assert "test_client_id" in response.headers["location"]


class TestAuthCallback:
    @patch("web.routes.auth.exchange_code")
    @patch("web.routes.auth.fetch_discord_user")
    @patch("web.routes.auth.fetch_user_guilds")
    def test_callback_issues_jwt(self, mock_guilds, mock_user, mock_exchange, client, fake_valkey):
        mock_exchange.return_value = {"access_token": "discord_tok", "expires_in": 604800}
        mock_user.return_value = {"id": "999", "username": "TestUser", "discriminator": "0"}
        mock_guilds.return_value = [
            {"id": "987654321", "name": "Test Guild", "icon": None, "permissions": 0x8}  # ADMINISTRATOR
        ]

        response = client.get("/api/auth/callback?code=test_code")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_callback_without_code_returns_422(self, client):
        response = client.get("/api/auth/callback")
        assert response.status_code == 422


class TestAuthMe:
    def test_me_without_auth_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_returns_user_info(self, client, fake_valkey):
        # Seed permission cache
        fake_valkey.set_permissions(
            "123456", {"987654321": {"level": "admin", "name": "Test Guild", "icon": None}}, ttl=300
        )

        headers = make_auth_header()
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "123456"
        assert data["username"] == "TestUser"
        assert len(data["guilds"]) == 1
