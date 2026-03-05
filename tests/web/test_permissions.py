from tests.web.conftest import make_auth_header


class TestPermissionEnforcement:
    def test_unauthenticated_returns_401(self, client):
        response = client.get("/api/guilds/")
        assert response.status_code == 401

    def test_invalid_jwt_returns_401(self, client):
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        response = client.get("/api/guilds/", headers=headers)
        assert response.status_code == 401

    def test_operator_routes_reject_non_operators(self, client, auth_header):
        """Regular user (ID 123456) is not in ops list (111222333)."""
        response = client.get("/api/operator/health", headers=auth_header)
        assert response.status_code == 403

    def test_operator_routes_accept_operators(self, client, operator_header, fake_valkey):
        """Operator user (ID 111222333) is in ops list."""
        # Health will return "unreachable" since no bot is running, but it shouldn't 403
        response = client.get("/api/operator/health", headers=operator_header)
        assert response.status_code == 200

    def test_guild_route_no_permissions_returns_403(self, client, auth_header, fake_valkey):
        """User has no guild permissions cached."""
        fake_valkey.set_permissions("123456", {}, ttl=300)
        response = client.get("/api/guilds/987654321/language", headers=auth_header)
        assert response.status_code == 403

    def test_guild_route_with_admin_returns_200(self, client, auth_header, fake_valkey, web_db_session):
        """User with admin permission can access guild routes."""
        fake_valkey.set_permissions("123456", {"987654321": "admin"}, ttl=300)
        response = client.get("/api/guilds/987654321/language", headers=auth_header)
        assert response.status_code == 200

    def test_operator_can_access_any_guild(self, client, operator_header, fake_valkey, web_db_session):
        """Operators can access any guild regardless of permissions."""
        fake_valkey.set_permissions("111222333", {}, ttl=300)
        response = client.get("/api/guilds/987654321/language", headers=operator_header)
        assert response.status_code == 200
