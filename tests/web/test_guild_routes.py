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


class TestLeaveMessageEndpoints:
    def test_get_default(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/leave-messages", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["channel_id"] is None

    def test_put_creates(self, client, auth_header):
        response = client.put(
            f"/api/guilds/{GUILD_ID}/leave-messages",
            json={"channel_id": "111222333", "message": "Bye {user}!", "enabled": True},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        assert response.json()["message"] == "Bye {user}!"

    def test_get_after_set(self, client, auth_header):
        client.put(
            f"/api/guilds/{GUILD_ID}/leave-messages",
            json={"channel_id": "111222333", "message": "Goodbye!", "enabled": True},
            headers=auth_header,
        )
        response = client.get(f"/api/guilds/{GUILD_ID}/leave-messages", headers=auth_header)
        assert response.json()["message"] == "Goodbye!"
        assert response.json()["channel_id"] == "111222333"


class TestAutoDeleteEndpoints:
    def test_get_empty_list(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/auto-delete", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_rule(self, client, auth_header):
        response = client.post(
            f"/api/guilds/{GUILD_ID}/auto-delete",
            json={"channel_id": "444555666", "keep_messages": 10, "delete_older_than": 86400},
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["channel_id"] == "444555666"
        assert data["keep_messages"] == 10

    def test_update_rule(self, client, auth_header):
        resp = client.post(
            f"/api/guilds/{GUILD_ID}/auto-delete",
            json={"channel_id": "444555666"},
            headers=auth_header,
        )
        rule_id = resp.json()["id"]
        response = client.put(
            f"/api/guilds/{GUILD_ID}/auto-delete/{rule_id}",
            json={"keep_messages": 50, "enabled": False},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["keep_messages"] == 50
        assert response.json()["enabled"] is False

    def test_delete_rule(self, client, auth_header):
        resp = client.post(
            f"/api/guilds/{GUILD_ID}/auto-delete",
            json={"channel_id": "444555666"},
            headers=auth_header,
        )
        rule_id = resp.json()["id"]
        response = client.delete(f"/api/guilds/{GUILD_ID}/auto-delete/{rule_id}", headers=auth_header)
        assert response.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, auth_header):
        response = client.delete(f"/api/guilds/{GUILD_ID}/auto-delete/9999", headers=auth_header)
        assert response.status_code == 404


class TestAutoKickerEndpoints:
    def test_get_default(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/auto-kicker", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["kick_after"] == 0
        assert data["enabled"] is False

    def test_put_creates(self, client, auth_header):
        response = client.put(
            f"/api/guilds/{GUILD_ID}/auto-kicker",
            json={"kick_after": 7, "enabled": True, "reminder_message": "You'll be kicked!"},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["kick_after"] == 7
        assert response.json()["enabled"] is True
