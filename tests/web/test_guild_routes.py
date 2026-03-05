import pytest

from tests.web.conftest import make_auth_header

GUILD_ID = 987654321


@pytest.fixture(autouse=True)
def seed_permissions(fake_valkey):
    """Give the default test user admin on the test guild."""
    fake_valkey.set_permissions("123456", {str(GUILD_ID): "admin"}, ttl=300)


class TestLanguageEndpoints:
    def test_get_language_default(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["language"] == "en"  # default

    def test_put_language(self, client, auth_header):
        response = client.put(
            f"/api/guilds/{GUILD_ID}/language",
            json={"language": "de"},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["language"] == "de"

    def test_get_language_after_set(self, client, auth_header):
        client.put(f"/api/guilds/{GUILD_ID}/language", json={"language": "fr"}, headers=auth_header)
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=auth_header)
        assert response.json()["language"] == "fr"


class TestModeratorRoleEndpoints:
    def test_get_empty_roles(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/moderator-roles", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == []

    def test_add_role(self, client, auth_header):
        response = client.post(
            f"/api/guilds/{GUILD_ID}/moderator-roles",
            json={"role_id": "555666777"},
            headers=auth_header,
        )
        assert response.status_code == 201

    def test_add_and_list_role(self, client, auth_header):
        client.post(f"/api/guilds/{GUILD_ID}/moderator-roles", json={"role_id": "555666777"}, headers=auth_header)
        response = client.get(f"/api/guilds/{GUILD_ID}/moderator-roles", headers=auth_header)
        roles = response.json()
        assert len(roles) == 1
        assert roles[0]["role_id"] == "555666777"

    def test_delete_role(self, client, auth_header):
        client.post(f"/api/guilds/{GUILD_ID}/moderator-roles", json={"role_id": "555666777"}, headers=auth_header)
        response = client.delete(f"/api/guilds/{GUILD_ID}/moderator-roles/555666777", headers=auth_header)
        assert response.status_code == 204

    def test_delete_nonexistent_role_returns_404(self, client, auth_header):
        response = client.delete(f"/api/guilds/{GUILD_ID}/moderator-roles/999", headers=auth_header)
        assert response.status_code == 404
