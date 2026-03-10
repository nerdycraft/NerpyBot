"""Tests for /api/wow/ proxy endpoints (realm search, guild validation)."""

from unittest.mock import patch


class TestWowRealmSearch:
    def test_requires_auth(self, client):
        response = client.get("/api/wow/realms?region=eu&q=black")
        assert response.status_code == 401

    def test_returns_realm_list(self, client, auth_header):
        with patch("web.routes.wow.send_bot_command_sync") as mock_send:
            mock_send.return_value = {"realms": [{"name": "Blackrock", "slug": "blackrock"}]}
            response = client.get("/api/wow/realms?region=eu&q=black", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["slug"] == "blackrock"

    def test_returns_503_when_bot_offline(self, client, auth_header):
        with patch("web.routes.wow.send_bot_command_sync") as mock_send:
            mock_send.return_value = None
            response = client.get("/api/wow/realms?region=eu&q=black", headers=auth_header)
        assert response.status_code == 503


class TestWowGuildValidate:
    def test_requires_auth(self, client):
        response = client.get("/api/wow/guilds/validate?region=eu&realm=blackrock&name=test")
        assert response.status_code == 401

    def test_valid_guild(self, client, auth_header):
        with patch("web.routes.wow.send_bot_command_sync") as mock_send:
            mock_send.return_value = {"valid": True, "display_name": "Test Guild"}
            response = client.get(
                "/api/wow/guilds/validate?region=eu&realm=blackrock&name=test",
                headers=auth_header,
            )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["display_name"] == "Test Guild"

    def test_invalid_guild(self, client, auth_header):
        with patch("web.routes.wow.send_bot_command_sync") as mock_send:
            mock_send.return_value = {"valid": False, "display_name": None}
            response = client.get(
                "/api/wow/guilds/validate?region=eu&realm=blackrock&name=notfound",
                headers=auth_header,
            )
        assert response.status_code == 200
        assert response.json()["valid"] is False

    def test_bot_offline_returns_503(self, client, auth_header):
        with patch("web.routes.wow.send_bot_command_sync") as mock_send:
            mock_send.return_value = None
            response = client.get(
                "/api/wow/guilds/validate?region=eu&realm=blackrock&name=test",
                headers=auth_header,
            )
        assert response.status_code == 503
