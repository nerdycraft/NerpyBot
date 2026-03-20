# -*- coding: utf-8 -*-
"""Tests for GuildConfigCache — language, modrole, reaction roles, and leave messages."""

from unittest.mock import MagicMock

import pytest

from utils.cache import GuildConfigCache


GUILD_ID = 987654321
GUILD_ID_2 = 111222333


@pytest.fixture
def cache():
    return GuildConfigCache()


@pytest.fixture
def session_factory(db_session):
    """Provide a session factory that always yields the test db_session."""
    factory = MagicMock()
    factory.return_value = db_session
    # The cache calls session.close() — make it a no-op so the session stays open
    db_session.close = MagicMock()
    return factory


# ── Language ──────────────────────────────────────────────────────────────────


class TestGuildLanguage:
    def test_miss_defaults_to_en(self, cache, session_factory):
        lang = cache.get_guild_language(GUILD_ID, session_factory)
        assert lang == "en"
        session_factory.assert_called_once()

    def test_miss_loads_from_db(self, cache, session_factory, db_session):
        from models.admin import GuildLanguageConfig

        db_session.add(GuildLanguageConfig(GuildId=GUILD_ID, Language="de"))
        db_session.commit()

        lang = cache.get_guild_language(GUILD_ID, session_factory)
        assert lang == "de"

    def test_hit_skips_db(self, cache, session_factory):
        cache.set_guild_language(GUILD_ID, "fr")
        lang = cache.get_guild_language(GUILD_ID, session_factory)
        assert lang == "fr"
        session_factory.assert_not_called()

    def test_set_overwrites(self, cache, session_factory):
        cache.set_guild_language(GUILD_ID, "de")
        cache.set_guild_language(GUILD_ID, "fr")
        lang = cache.get_guild_language(GUILD_ID, session_factory)
        assert lang == "fr"
        session_factory.assert_not_called()

    def test_second_call_uses_cache(self, cache, session_factory, db_session):
        from models.admin import GuildLanguageConfig

        db_session.add(GuildLanguageConfig(GuildId=GUILD_ID, Language="de"))
        db_session.commit()

        cache.get_guild_language(GUILD_ID, session_factory)
        cache.get_guild_language(GUILD_ID, session_factory)  # should be cached

        assert session_factory.call_count == 1

    def test_different_guilds_are_independent(self, cache, session_factory, db_session):
        from models.admin import GuildLanguageConfig

        db_session.add(GuildLanguageConfig(GuildId=GUILD_ID, Language="de"))
        db_session.add(GuildLanguageConfig(GuildId=GUILD_ID_2, Language="fr"))
        db_session.commit()

        assert cache.get_guild_language(GUILD_ID, session_factory) == "de"
        assert cache.get_guild_language(GUILD_ID_2, session_factory) == "fr"


# ── Moderator role ────────────────────────────────────────────────────────────


class TestModrole:
    def test_miss_returns_none_when_no_entry(self, cache, session_factory):
        role_id = cache.get_modrole(GUILD_ID, session_factory)
        assert role_id is None
        session_factory.assert_called_once()

    def test_miss_loads_from_db(self, cache, session_factory, db_session):
        from models.admin import BotModeratorRole

        db_session.add(BotModeratorRole(GuildId=GUILD_ID, RoleId=555))
        db_session.commit()

        role_id = cache.get_modrole(GUILD_ID, session_factory)
        assert role_id == 555

    def test_hit_skips_db(self, cache, session_factory):
        cache.set_modrole(GUILD_ID, 555)
        role_id = cache.get_modrole(GUILD_ID, session_factory)
        assert role_id == 555
        session_factory.assert_not_called()

    def test_set_none_is_cached(self, cache, session_factory):
        # Explicitly set None (no modrole) — should still cache and skip DB
        cache.set_modrole(GUILD_ID, None)
        role_id = cache.get_modrole(GUILD_ID, session_factory)
        assert role_id is None
        session_factory.assert_not_called()

    def test_delete_forces_next_miss(self, cache, session_factory):
        cache.set_modrole(GUILD_ID, 555)
        cache.delete_modrole(GUILD_ID)
        cache.get_modrole(GUILD_ID, session_factory)
        session_factory.assert_called_once()

    def test_delete_nonexistent_is_safe(self, cache):
        cache.delete_modrole(GUILD_ID)  # must not raise


# ── Reaction roles ────────────────────────────────────────────────────────────


class TestReactionRoles:
    def test_unwarmed_always_returns_true(self, cache):
        assert cache.is_reaction_role_message(999999) is True

    def test_warmed_returns_false_for_unknown(self, cache, session_factory):
        cache.warm_reaction_roles(session_factory)
        assert cache.is_reaction_role_message(999999) is False

    def test_warmed_returns_true_for_known(self, cache, session_factory, db_session):
        from models.reactionrole import ReactionRoleMessage

        db_session.add(ReactionRoleMessage(GuildId=GUILD_ID, ChannelId=111, MessageId=42))
        db_session.commit()

        cache.warm_reaction_roles(session_factory)
        assert cache.is_reaction_role_message(42) is True

    def test_add_after_warm(self, cache, session_factory):
        cache.warm_reaction_roles(session_factory)
        assert cache.is_reaction_role_message(77) is False
        cache.add_reaction_role_message(GUILD_ID, 77)
        assert cache.is_reaction_role_message(77) is True

    def test_remove_after_add(self, cache, session_factory):
        cache.warm_reaction_roles(session_factory)
        cache.add_reaction_role_message(GUILD_ID, 77)
        cache.remove_reaction_role_message(GUILD_ID, 77)
        assert cache.is_reaction_role_message(77) is False

    def test_remove_nonexistent_is_safe(self, cache):
        cache.remove_reaction_role_message(GUILD_ID, 999)  # must not raise

    def test_warm_is_idempotent(self, cache, session_factory, db_session):
        from models.reactionrole import ReactionRoleMessage

        db_session.add(ReactionRoleMessage(GuildId=GUILD_ID, ChannelId=111, MessageId=42))
        db_session.commit()

        cache.warm_reaction_roles(session_factory)
        cache.add_reaction_role_message(GUILD_ID, 99)  # locally added

        cache.warm_reaction_roles(session_factory)  # re-warm clears local addition
        assert cache.is_reaction_role_message(99) is False
        assert cache.is_reaction_role_message(42) is True


# ── Leave messages ────────────────────────────────────────────────────────────


class TestLeaveMessages:
    def test_unwarmed_always_returns_true(self, cache):
        assert cache.is_leave_message_guild(GUILD_ID) is True

    def test_warmed_returns_false_for_unknown(self, cache, session_factory):
        cache.warm_leave_messages(session_factory)
        assert cache.is_leave_message_guild(GUILD_ID) is False

    def test_warmed_returns_true_for_enabled_guild(self, cache, session_factory, db_session):
        from models.leavemsg import LeaveMessage

        db_session.add(LeaveMessage(GuildId=GUILD_ID, ChannelId=111, Message="bye", Enabled=True))
        db_session.commit()

        cache.warm_leave_messages(session_factory)
        assert cache.is_leave_message_guild(GUILD_ID) is True

    def test_disabled_guild_not_in_cache(self, cache, session_factory, db_session):
        from models.leavemsg import LeaveMessage

        db_session.add(LeaveMessage(GuildId=GUILD_ID, ChannelId=111, Message="bye", Enabled=False))
        db_session.commit()

        cache.warm_leave_messages(session_factory)
        assert cache.is_leave_message_guild(GUILD_ID) is False

    def test_set_enabled(self, cache, session_factory):
        cache.warm_leave_messages(session_factory)
        cache.set_leave_message_guild(GUILD_ID, True, channel_id=111, message="bye")
        assert cache.is_leave_message_guild(GUILD_ID) is True

    def test_set_disabled(self, cache, session_factory):
        cache.warm_leave_messages(session_factory)
        cache.set_leave_message_guild(GUILD_ID, True, channel_id=111, message="bye")
        cache.set_leave_message_guild(GUILD_ID, False)
        assert cache.is_leave_message_guild(GUILD_ID) is False

    def test_warm_is_idempotent(self, cache, session_factory, db_session):
        from models.leavemsg import LeaveMessage

        db_session.add(LeaveMessage(GuildId=GUILD_ID, ChannelId=111, Message="bye", Enabled=True))
        db_session.commit()

        cache.warm_leave_messages(session_factory)
        cache.set_leave_message_guild(GUILD_ID_2, True, channel_id=222, message="cya")  # local addition

        cache.warm_leave_messages(session_factory)  # re-warm clears local addition
        assert cache.is_leave_message_guild(GUILD_ID_2) is False
        assert cache.is_leave_message_guild(GUILD_ID) is True


# ── Eviction ──────────────────────────────────────────────────────────────────


class TestEviction:
    def test_evict_clears_language(self, cache, session_factory):
        cache.set_guild_language(GUILD_ID, "de")
        cache.evict_guild(GUILD_ID)
        cache.get_guild_language(GUILD_ID, session_factory)
        session_factory.assert_called_once()

    def test_evict_clears_modrole(self, cache, session_factory):
        cache.set_modrole(GUILD_ID, 555)
        cache.evict_guild(GUILD_ID)
        cache.get_modrole(GUILD_ID, session_factory)
        session_factory.assert_called_once()

    def test_evict_removes_from_leave_guild_set(self, cache, session_factory):
        cache.warm_leave_messages(session_factory)
        cache.set_leave_message_guild(GUILD_ID, True, channel_id=111, message="bye")
        cache.evict_guild(GUILD_ID)
        assert cache.is_leave_message_guild(GUILD_ID) is False

    def test_evict_removes_reaction_role_messages(self, cache, session_factory):
        cache.warm_reaction_roles(session_factory)
        cache.add_reaction_role_message(GUILD_ID, 42)
        cache.add_reaction_role_message(GUILD_ID_2, 99)
        cache.evict_guild(GUILD_ID)
        assert cache.is_reaction_role_message(42) is False  # evicted
        assert cache.is_reaction_role_message(99) is True  # other guild unaffected

    def test_evict_nonexistent_is_safe(self, cache):
        cache.evict_guild(GUILD_ID)  # must not raise

    def test_evict_does_not_affect_other_guilds(self, cache, session_factory):
        cache.set_guild_language(GUILD_ID, "de")
        cache.set_guild_language(GUILD_ID_2, "fr")
        cache.evict_guild(GUILD_ID)
        lang = cache.get_guild_language(GUILD_ID_2, session_factory)
        assert lang == "fr"
        session_factory.assert_not_called()
