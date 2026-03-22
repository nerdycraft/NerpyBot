from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from tests.web.conftest import make_auth_header

GUILD_ID = 987654321


@pytest.fixture(autouse=True)
def seed_permissions(fake_valkey):
    """Give the default test user admin on the test guild."""
    fake_valkey.set_permissions(
        "123456", {str(GUILD_ID): {"level": "admin", "name": "Test Guild", "icon": None}}, ttl=300
    )


@pytest.fixture(autouse=True)
def seed_premium_user(web_db_session):
    """Grant premium to the default test user so guild endpoints pass require_premium."""
    from models.admin import PremiumUser

    PremiumUser.grant(123456, 111222333, web_db_session)
    web_db_session.commit()


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

    def test_put_language_write_through_and_notifies_bot(self, client, fake_valkey, auth_header):
        """PUT language must populate _guild_lang_cache and publish set_guild_language to the bot."""
        import json
        from unittest.mock import patch
        from web.routes.guilds import _guild_lang_cache

        # Pre-populate cache with stale value to confirm write-through replaces it.
        _guild_lang_cache[GUILD_ID] = "stale"

        published = []

        def capture(channel, message):
            published.append((channel, message))

        with patch.object(fake_valkey._client, "publish", side_effect=capture):
            response = client.put(
                f"/api/guilds/{GUILD_ID}/language",
                json={"language": "de"},
                headers=auth_header,
            )

        assert response.status_code == 200
        assert _guild_lang_cache[GUILD_ID] == "de"
        bot_cmds = [json.loads(msg) for ch, msg in published if ch == "nerpybot:cmd"]
        lang_cmds = [c for c in bot_cmds if c.get("command") == "set_guild_language"]
        assert len(lang_cmds) == 1
        assert lang_cmds[0]["guild_id"] == str(GUILD_ID)
        assert lang_cmds[0]["language"] == "de"


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

    def test_post_notifies_bot_to_invalidate_cache(self, client, fake_valkey, auth_header):
        """POST moderator-roles must publish an invalidate_modrole command with the new role_id."""
        import json
        from unittest.mock import patch

        published = []

        def capture(channel, message):
            published.append((channel, message))

        with patch.object(fake_valkey._client, "publish", side_effect=capture):
            response = client.post(
                f"/api/guilds/{GUILD_ID}/moderator-roles",
                json={"role_id": "555666777"},
                headers=auth_header,
            )

        assert response.status_code == 201
        bot_cmds = [json.loads(msg) for ch, msg in published if ch == "nerpybot:cmd"]
        invalidations = [c for c in bot_cmds if c.get("command") == "invalidate_modrole"]
        assert len(invalidations) == 1
        assert invalidations[0]["guild_id"] == str(GUILD_ID)

    def test_delete_notifies_bot_to_invalidate_cache(self, client, fake_valkey, auth_header):
        """DELETE moderator-roles must publish an invalidate_modrole command with null role_id."""
        import json
        from unittest.mock import patch

        client.post(
            f"/api/guilds/{GUILD_ID}/moderator-roles",
            json={"role_id": "555666777"},
            headers=auth_header,
        )

        published = []

        def capture(channel, message):
            published.append((channel, message))

        with patch.object(fake_valkey._client, "publish", side_effect=capture):
            response = client.delete(
                f"/api/guilds/{GUILD_ID}/moderator-roles/555666777",
                headers=auth_header,
            )

        assert response.status_code == 204
        bot_cmds = [json.loads(msg) for ch, msg in published if ch == "nerpybot:cmd"]
        invalidations = [c for c in bot_cmds if c.get("command") == "invalidate_modrole"]
        assert len(invalidations) == 1
        assert invalidations[0]["guild_id"] == str(GUILD_ID)


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
            json={"channel_id": "111222333", "message": "Bye {member}!", "enabled": True},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        assert response.json()["message"] == "Bye {member}!"

    def test_get_after_set(self, client, auth_header):
        client.put(
            f"/api/guilds/{GUILD_ID}/leave-messages",
            json={"channel_id": "111222333", "message": "Goodbye {member}!", "enabled": True},
            headers=auth_header,
        )
        response = client.get(f"/api/guilds/{GUILD_ID}/leave-messages", headers=auth_header)
        assert response.json()["message"] == "Goodbye {member}!"
        assert response.json()["channel_id"] == "111222333"

    def test_put_rejects_missing_placeholder(self, client, auth_header):
        response = client.put(
            f"/api/guilds/{GUILD_ID}/leave-messages",
            json={"message": "Goodbye!"},
            headers=auth_header,
        )
        assert response.status_code == 422

    def test_put_notifies_bot_to_invalidate_cache(self, client, fake_valkey, auth_header):
        """PUT leave-messages must publish an invalidate_leave_config command to the bot."""
        import json
        from unittest.mock import patch

        published = []

        def capture(channel, message):
            published.append((channel, message))

        with patch.object(fake_valkey._client, "publish", side_effect=capture):
            response = client.put(
                f"/api/guilds/{GUILD_ID}/leave-messages",
                json={"channel_id": "111222333", "message": "Bye {member}!", "enabled": True},
                headers=auth_header,
            )

        assert response.status_code == 200
        bot_cmds = [json.loads(msg) for ch, msg in published if ch == "nerpybot:cmd"]
        invalidations = [c for c in bot_cmds if c.get("command") == "invalidate_leave_config"]
        assert len(invalidations) == 1
        assert invalidations[0]["guild_id"] == str(GUILD_ID)


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
        assert data["crafting_boards"] == []

    def test_get_includes_stats_fields(self, client, auth_header, web_db_session):
        from models.wow import WowGuildNewsConfig

        cfg = WowGuildNewsConfig(
            GuildId=GUILD_ID,
            ChannelId=111,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            ActiveDays=7,
            MinLevel=10,
            Enabled=True,
        )
        web_db_session.add(cfg)
        web_db_session.commit()

        response = client.get(f"/api/guilds/{GUILD_ID}/wow", headers=auth_header)
        data = response.json()
        assert len(data["guild_news"]) == 1
        gn = data["guild_news"][0]
        assert gn["min_level"] == 10
        assert gn["active_days"] == 7
        assert gn["tracked_characters"] == 0
        assert gn["last_activity"] is None


class TestWowNewsConfigCRUD:
    def test_create_news_config(self, client, auth_header, web_db_session):
        body = {
            "channel_id": "111",
            "wow_guild_name": "Test Guild",
            "wow_realm_slug": "blackrock",
            "region": "eu",
            "active_days": 5,
            "min_level": 20,
        }
        response = client.post(
            f"/api/guilds/{GUILD_ID}/wow/news-configs",
            json=body,
            headers=auth_header,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["wow_guild_name"] == "Test Guild"  # display name preserved
        assert data["active_days"] == 5
        assert data["min_level"] == 20

    def test_create_duplicate_returns_409(self, client, auth_header, web_db_session):
        from models.wow import WowGuildNewsConfig

        cfg = WowGuildNewsConfig(
            GuildId=GUILD_ID,
            ChannelId=111,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            ActiveDays=7,
            MinLevel=10,
            Enabled=True,
        )
        web_db_session.add(cfg)
        web_db_session.commit()

        body = {
            "channel_id": "111",
            "wow_guild_name": "test-guild",
            "wow_realm_slug": "blackrock",
            "region": "eu",
        }
        response = client.post(
            f"/api/guilds/{GUILD_ID}/wow/news-configs",
            json=body,
            headers=auth_header,
        )
        assert response.status_code == 409

    def test_patch_news_config(self, client, auth_header, web_db_session):
        from models.wow import WowGuildNewsConfig

        cfg = WowGuildNewsConfig(
            GuildId=GUILD_ID,
            ChannelId=111,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            ActiveDays=7,
            MinLevel=10,
            Enabled=True,
        )
        web_db_session.add(cfg)
        web_db_session.commit()

        response = client.patch(
            f"/api/guilds/{GUILD_ID}/wow/news-configs/{cfg.Id}",
            json={"active_days": 14, "enabled": False},
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_days"] == 14
        assert data["enabled"] is False

    def test_patch_not_found(self, client, auth_header):
        response = client.patch(
            f"/api/guilds/{GUILD_ID}/wow/news-configs/99999",
            json={"active_days": 14},
            headers=auth_header,
        )
        assert response.status_code == 404

    def test_delete_news_config(self, client, auth_header, web_db_session):
        from models.wow import WowGuildNewsConfig

        cfg = WowGuildNewsConfig(
            GuildId=GUILD_ID,
            ChannelId=111,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            ActiveDays=7,
            MinLevel=10,
            Enabled=True,
        )
        web_db_session.add(cfg)
        web_db_session.commit()
        cfg_id = cfg.Id

        response = client.delete(
            f"/api/guilds/{GUILD_ID}/wow/news-configs/{cfg_id}",
            headers=auth_header,
        )
        assert response.status_code == 204

        from models.wow import WowGuildNewsConfig as WGN

        assert web_db_session.query(WGN).filter(WGN.Id == cfg_id).first() is None

    def test_roster_empty(self, client, auth_header, web_db_session):
        from models.wow import WowGuildNewsConfig

        cfg = WowGuildNewsConfig(
            GuildId=GUILD_ID,
            ChannelId=111,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            ActiveDays=7,
            MinLevel=10,
            Enabled=True,
        )
        web_db_session.add(cfg)
        web_db_session.commit()

        response = client.get(
            f"/api/guilds/{GUILD_ID}/wow/news-configs/{cfg.Id}/roster",
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_roster_returns_characters(self, client, auth_header, web_db_session):
        import json
        from datetime import datetime

        from models.wow import WowCharacterMounts, WowGuildNewsConfig

        cfg = WowGuildNewsConfig(
            GuildId=GUILD_ID,
            ChannelId=111,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            ActiveDays=7,
            MinLevel=10,
            Enabled=True,
        )
        web_db_session.add(cfg)
        web_db_session.flush()

        mount = WowCharacterMounts(
            ConfigId=cfg.Id,
            CharacterName="Testchar",
            RealmSlug="blackrock",
            KnownMountIds=json.dumps([1, 2, 3]),
            LastChecked=datetime(2026, 3, 9, 12, 0, 0),
        )
        web_db_session.add(mount)
        web_db_session.commit()

        response = client.get(
            f"/api/guilds/{GUILD_ID}/wow/news-configs/{cfg.Id}/roster",
            headers=auth_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["character_name"] == "Testchar"
        assert data[0]["mount_count"] == 3


class TestSupportModeGuildAccess:
    """Tests for operator support_mode logic in require_guild_access."""

    def test_operator_with_real_guild_perms_gets_normal_access(self, client, fake_valkey):
        """Operator with admin/mod perms on the guild → no support_mode, normal 200."""
        # Seed admin perms for the operator (user_id=111222333) on this guild
        fake_valkey.set_permissions("111222333", {str(GUILD_ID): {"level": "admin", "name": "Test Guild"}}, ttl=300)
        header = make_auth_header(user_id="111222333", username="Operator")
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=header)
        assert response.status_code == 200
        # No support_mode key in the language response body (it's a user-dict concern, not response body)
        data = response.json()
        assert "language" in data

    def test_operator_without_guild_perms_gets_support_mode(self, client, fake_valkey):
        """Operator with no guild permissions → still 200 (access granted), but support_mode=True on user dict.

        We verify the endpoint still returns 200 — the support_mode flag is on the internal user dict
        and will be used in Step 5. For now, 200 confirms the operator bypassed the 403 gate.
        """
        # Empty perms for operator — no entry for this guild
        fake_valkey.set_permissions("111222333", {}, ttl=300)
        header = make_auth_header(user_id="111222333", username="Operator")
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=header)
        assert response.status_code == 200

    def test_operator_without_any_cached_perms_gets_support_mode(self, client, fake_valkey):
        """Operator with no cached permission entry at all → still 200, support_mode path."""
        # No permissions seeded for operator at all (get_permissions returns None)
        header = make_auth_header(user_id="111222333", username="Operator")
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=header)
        assert response.status_code == 200

    def test_non_operator_without_guild_perms_is_rejected(self, client, fake_valkey, web_db_session):
        """Non-operator with no guild permissions → 403 from require_guild_access (not require_premium)."""
        from models.admin import PremiumUser

        # Grant premium so the request passes require_premium and reaches require_guild_access
        PremiumUser.grant(999888777, 111222333, web_db_session)
        web_db_session.commit()
        # Seed perms with no entry for this guild for the regular user
        fake_valkey.set_permissions("999888777", {}, ttl=300)
        header = make_auth_header(user_id="999888777", username="RandomUser")
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=header)
        assert response.status_code == 403
        assert "guild" in response.json()["detail"].lower()


class TestSupportModeRedactionAndWriteBlocking:
    """Tests for support_mode PII redaction on GET and write-blocking on POST/PUT/DELETE."""

    @pytest.fixture
    def support_header(self, fake_valkey):
        """Auth header for an operator in support mode (no guild permissions cached)."""
        # Operator (111222333) with empty perms → no entry for GUILD_ID → support_mode=True
        fake_valkey.set_permissions("111222333", {}, ttl=300)
        return make_auth_header(user_id="111222333", username="Operator")

    @pytest.fixture
    def admin_header(self, fake_valkey):
        """Auth header for an operator WITH real guild admin perms (no redaction, writes allowed)."""
        fake_valkey.set_permissions("111222333", {str(GUILD_ID): {"level": "admin", "name": "Test Guild"}}, ttl=300)
        return make_auth_header(user_id="111222333", username="Operator")

    def test_get_reminders_in_support_mode_redacts_author(self, client, support_header, web_db_session):
        """GET reminders in support mode → author is [redacted], message is NOT redacted."""
        from datetime import UTC, datetime

        from models.reminder import ReminderMessage

        reminder = ReminderMessage(
            GuildId=GUILD_ID,
            ChannelId=111,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="RealUserName",
            Message="Hello, world!",
            Enabled=True,
            NextFire=datetime.now(UTC),
            ScheduleType="daily",
        )
        web_db_session.add(reminder)
        web_db_session.commit()

        response = client.get(f"/api/guilds/{GUILD_ID}/reminders", headers=support_header)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["author"] == "[redacted]"
        # message is bot-authored config, NOT PII — must not be redacted
        assert data[0]["message"] == "Hello, world!"

    def test_get_reminders_in_support_mode_sets_header(self, client, support_header):
        """GET reminders in support mode → X-Support-Mode: true response header."""
        response = client.get(f"/api/guilds/{GUILD_ID}/reminders", headers=support_header)
        assert response.status_code == 200
        assert response.headers.get("x-support-mode") == "true"

    def test_get_language_in_support_mode_sets_header(self, client, support_header):
        """GET language in support mode → X-Support-Mode: true response header."""
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=support_header)
        assert response.status_code == 200
        assert response.headers.get("x-support-mode") == "true"

    def test_put_language_in_support_mode_is_blocked(self, client, support_header):
        """PUT language in support mode → 403 Read-only in support mode."""
        response = client.put(
            f"/api/guilds/{GUILD_ID}/language",
            json={"language": "de"},
            headers=support_header,
        )
        assert response.status_code == 403
        assert "Read-only in support mode" in response.json()["detail"]

    def test_post_reminder_in_support_mode_is_blocked(self, client, support_header):
        """POST reminder in support mode → 403."""
        response = client.post(
            f"/api/guilds/{GUILD_ID}/reminders",
            json={
                "channel_id": "111",
                "message": "Test",
                "schedule_type": "interval",
                "interval_seconds": 3600,
                "timezone": "UTC",
            },
            headers=support_header,
        )
        assert response.status_code == 403
        assert "Read-only in support mode" in response.json()["detail"]

    def test_delete_reminder_in_support_mode_is_blocked(self, client, support_header, web_db_session):
        """DELETE reminder in support mode → 403."""
        from datetime import UTC, datetime

        from models.reminder import ReminderMessage

        reminder = ReminderMessage(
            GuildId=GUILD_ID,
            ChannelId=111,
            CreateDate=datetime.now(UTC),
            Message="Test",
            Enabled=True,
            NextFire=datetime.now(UTC),
            ScheduleType="daily",
        )
        web_db_session.add(reminder)
        web_db_session.commit()

        response = client.delete(f"/api/guilds/{GUILD_ID}/reminders/{reminder.Id}", headers=support_header)
        assert response.status_code == 403
        assert "Read-only in support mode" in response.json()["detail"]

    def test_operator_with_real_perms_reads_without_redaction(self, client, admin_header, web_db_session):
        """Operator with real admin perms → author is NOT redacted, no support-mode header."""
        from datetime import UTC, datetime

        from models.reminder import ReminderMessage

        reminder = ReminderMessage(
            GuildId=GUILD_ID,
            ChannelId=111,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="RealUserName",
            Message="Hello, world!",
            Enabled=True,
            NextFire=datetime.now(UTC),
            ScheduleType="daily",
        )
        web_db_session.add(reminder)
        web_db_session.commit()

        response = client.get(f"/api/guilds/{GUILD_ID}/reminders", headers=admin_header)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["author"] == "RealUserName"
        assert "x-support-mode" not in response.headers

    def test_operator_with_real_perms_can_write(self, client, admin_header):
        """Operator with real admin perms → PUT language succeeds (no 403)."""
        response = client.put(
            f"/api/guilds/{GUILD_ID}/language",
            json={"language": "de"},
            headers=admin_header,
        )
        assert response.status_code == 200
        assert response.json()["language"] == "de"


class TestPremiumCacheBehavior:
    """Tests for the in-process premium user ID cache in web/dependencies.py."""

    def test_get_premium_ids_db_failure_returns_503(self, client, auth_header):
        """When PremiumUser.get_all raises SQLAlchemyError, guild routes must return 503."""
        from web.dependencies import _premium_ids_cache

        _premium_ids_cache.clear()  # force cache miss so DB is actually hit
        with patch("models.admin.PremiumUser.get_all", side_effect=SQLAlchemyError("DB down")):
            response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=auth_header)
        assert response.status_code == 503

    def test_invalidate_premium_cache_forces_fresh_db_read(self, client, fake_valkey, web_db_session):
        """invalidate_premium_cache forces the next request to reload from DB.

        Flow: new user has no premium → 403; grant premium + invalidate → 200.
        """
        from models.admin import PremiumUser
        from web.dependencies import _premium_ids_cache, invalidate_premium_cache

        new_user_id = 555444333
        fake_valkey.set_permissions(
            str(new_user_id),
            {str(GUILD_ID): {"level": "admin", "name": "Test Guild"}},
            ttl=300,
        )
        new_header = make_auth_header(user_id=str(new_user_id), username="NewUser")

        # Without premium — 403
        _premium_ids_cache.clear()
        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=new_header)
        assert response.status_code == 403

        # Grant premium and invalidate so the next request hits DB
        PremiumUser.grant(new_user_id, 111222333, web_db_session)
        web_db_session.commit()
        invalidate_premium_cache()

        response = client.get(f"/api/guilds/{GUILD_ID}/language", headers=new_header)
        assert response.status_code == 200
