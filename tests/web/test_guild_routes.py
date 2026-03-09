import pytest


GUILD_ID = 987654321


@pytest.fixture(autouse=True)
def seed_permissions(fake_valkey):
    """Give the default test user admin on the test guild."""
    fake_valkey.set_permissions(
        "123456", {str(GUILD_ID): {"level": "admin", "name": "Test Guild", "icon": None}}, ttl=300
    )


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


class TestReactionRoleEndpoints:
    def test_get_empty(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/reaction-roles", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_with_data(self, client, auth_header, web_db_session):
        from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage

        msg = ReactionRoleMessage(GuildId=GUILD_ID, ChannelId=111, MessageId=222)
        web_db_session.add(msg)
        web_db_session.flush()
        entry = ReactionRoleEntry(ReactionRoleMessageId=msg.Id, Emoji="👍", RoleId=333)
        web_db_session.add(entry)
        web_db_session.commit()

        response = client.get(f"/api/guilds/{GUILD_ID}/reaction-roles", headers=auth_header)
        data = response.json()
        assert len(data) == 1
        assert data[0]["message_id"] == "222"
        assert len(data[0]["entries"]) == 1
        assert data[0]["entries"][0]["emoji"] == "👍"


class TestRoleMappingEndpoints:
    def test_get_empty(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/role-mappings", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_and_list(self, client, auth_header):
        client.post(
            f"/api/guilds/{GUILD_ID}/role-mappings",
            json={"source_role_id": "100", "target_role_id": "200"},
            headers=auth_header,
        )
        response = client.get(f"/api/guilds/{GUILD_ID}/role-mappings", headers=auth_header)
        data = response.json()
        assert len(data) == 1
        assert data[0]["source_role_id"] == "100"

    def test_delete_mapping(self, client, auth_header):
        resp = client.post(
            f"/api/guilds/{GUILD_ID}/role-mappings",
            json={"source_role_id": "100", "target_role_id": "200"},
            headers=auth_header,
        )
        mapping_id = resp.json()["id"]
        response = client.delete(f"/api/guilds/{GUILD_ID}/role-mappings/{mapping_id}", headers=auth_header)
        assert response.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, auth_header):
        response = client.delete(f"/api/guilds/{GUILD_ID}/role-mappings/9999", headers=auth_header)
        assert response.status_code == 404


class TestReminderEndpoints:
    def test_get_empty(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/reminders", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_with_data(self, client, auth_header, web_db_session):
        from datetime import UTC, datetime

        from models.reminder import ReminderMessage

        reminder = ReminderMessage(
            GuildId=GUILD_ID,
            ChannelId=111,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            Message="Don't forget!",
            Enabled=True,
            Count=5,
            NextFire=datetime.now(UTC),
            ScheduleType="daily",
        )
        web_db_session.add(reminder)
        web_db_session.commit()

        response = client.get(f"/api/guilds/{GUILD_ID}/reminders", headers=auth_header)
        data = response.json()
        assert len(data) == 1
        assert data[0]["message"] == "Don't forget!"
        assert data[0]["schedule_type"] == "daily"


class TestApplicationFormEndpoints:
    def test_get_empty(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/application-forms", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_with_data(self, client, auth_header, web_db_session):
        from models.application import ApplicationForm, ApplicationQuestion

        form = ApplicationForm(
            GuildId=GUILD_ID,
            Name="Apply",
            RequiredApprovals=2,
            RequiredDenials=1,
        )
        web_db_session.add(form)
        web_db_session.flush()
        q = ApplicationQuestion(FormId=form.Id, QuestionText="Why join?", SortOrder=1)
        web_db_session.add(q)
        web_db_session.commit()

        response = client.get(f"/api/guilds/{GUILD_ID}/application-forms", headers=auth_header)
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Apply"
        assert len(data[0]["questions"]) == 1


class TestWowEndpoints:
    def test_get_empty(self, client, auth_header):
        response = client.get(f"/api/guilds/{GUILD_ID}/wow", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert data["guild_news"] == []
        assert data["crafting_board"] is None
