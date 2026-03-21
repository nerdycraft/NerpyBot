# -*- coding: utf-8 -*-
"""Tests for GuildConfigCache — language, modrole, reaction roles, and leave messages."""

from unittest.mock import MagicMock

import pytest

from utils.cache import GuildConfigCache, build_name_choices


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

    def test_db_failure_leaves_flag_unset(self, cache):
        def failing_factory():
            raise Exception("DB down")

        with pytest.raises(Exception, match="DB down"):
            cache.warm_reaction_roles(failing_factory)

        assert cache._rr_warmed is False
        assert cache.is_reaction_role_message(99999) is True

    def test_can_rewarm_after_failure(self, cache, session_factory):
        def failing_factory():
            raise Exception("DB down")

        with pytest.raises(Exception):
            cache.warm_reaction_roles(failing_factory)

        cache.warm_reaction_roles(session_factory)
        assert cache._rr_warmed is True

    def test_add_reaction_role_entry_before_warm_is_noop(self, cache):
        # Before warm-up, add_reaction_role_entry must not raise and must not populate mappings.
        cache.add_reaction_role_entry(42, "👍", 777)
        assert 42 not in cache._rr_mappings


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

    def test_get_leave_config_unwarmed_hits_db(self, cache, session_factory, db_session):
        from models.leavemsg import LeaveMessage

        db_session.add(LeaveMessage(GuildId=GUILD_ID, ChannelId=111, Message="bye {member}", Enabled=True))
        db_session.commit()

        # cache is cold — should fall back to DB
        result = cache.get_leave_config(GUILD_ID, session_factory)
        assert result == (111, "bye {member}")

    def test_get_leave_config_unwarmed_returns_none_when_absent(self, cache, session_factory):
        result = cache.get_leave_config(GUILD_ID, session_factory)
        assert result is None

    def test_get_leave_config_unwarmed_caches_none_result(self, cache, session_factory):
        # First call hits DB (no row), stores None; second call must not hit DB again.
        cache.get_leave_config(GUILD_ID, session_factory)

        # Patch session_factory to detect a second DB call
        db_called = []
        original = session_factory

        def spy_factory():
            db_called.append(True)
            return original()

        cache.get_leave_config(GUILD_ID, spy_factory)
        assert not db_called, "second call for same guild should not open a DB session"

    def test_get_leave_config_warmed_uses_cache(self, cache, session_factory, db_session):
        from models.leavemsg import LeaveMessage

        db_session.add(LeaveMessage(GuildId=GUILD_ID, ChannelId=111, Message="bye", Enabled=True))
        db_session.commit()

        cache.warm_leave_messages(session_factory)
        result = cache.get_leave_config(GUILD_ID, session_factory)
        assert result == (111, "bye")

    def test_set_enabled_without_channel_raises(self, cache):
        with pytest.raises(ValueError, match="channel_id is required"):
            cache.set_leave_message_guild(GUILD_ID, True, channel_id=None)

    def test_db_failure_leaves_flag_unset(self, cache):
        def failing_factory():
            raise Exception("DB down")

        with pytest.raises(Exception, match="DB down"):
            cache.warm_leave_messages(failing_factory)

        assert cache._leave_warmed is False
        assert cache.is_leave_message_guild(GUILD_ID) is True

    def test_can_rewarm_after_failure(self, cache, session_factory):
        def failing_factory():
            raise Exception("DB down")

        with pytest.raises(Exception):
            cache.warm_leave_messages(failing_factory)

        cache.warm_leave_messages(session_factory)
        assert cache._leave_warmed is True


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


# ── build_name_choices ────────────────────────────────────────────────────────


# ── get_reaction_role ─────────────────────────────────────────────────────────


class TestGetReactionRole:
    def test_returns_cache_miss_before_warm(self, cache):
        from utils.cache import REACTION_ROLE_CACHE_MISS

        assert cache.get_reaction_role(99, "👍") is REACTION_ROLE_CACHE_MISS

    def test_returns_role_id_after_warm(self, cache, session_factory, db_session):
        from models.reactionrole import ReactionRoleEntry, ReactionRoleMessage
        from utils.cache import REACTION_ROLE_CACHE_MISS

        msg = ReactionRoleMessage(GuildId=GUILD_ID, ChannelId=111, MessageId=42)
        db_session.add(msg)
        db_session.flush()
        db_session.add(ReactionRoleEntry(ReactionRoleMessageId=msg.Id, Emoji="👍", RoleId=777))
        db_session.commit()

        cache.warm_reaction_roles(session_factory)

        result = cache.get_reaction_role(42, "👍")
        assert result is not REACTION_ROLE_CACHE_MISS
        assert result == 777

    def test_returns_none_for_unknown_emoji_after_warm(self, cache, session_factory, db_session):
        from models.reactionrole import ReactionRoleMessage
        from utils.cache import REACTION_ROLE_CACHE_MISS

        db_session.add(ReactionRoleMessage(GuildId=GUILD_ID, ChannelId=111, MessageId=42))
        db_session.commit()

        cache.warm_reaction_roles(session_factory)

        result = cache.get_reaction_role(42, "🔥")
        assert result is not REACTION_ROLE_CACHE_MISS
        assert result is None


# ── cached_autocomplete ────────────────────────────────────────────────────────


class TestCachedAutocomplete:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        from utils.cache import _autocomplete_cache

        _autocomplete_cache.clear()
        yield
        _autocomplete_cache.clear()

    @pytest.mark.asyncio
    async def test_hit_returns_cached_result(self):
        from utils.cache import cached_autocomplete

        calls = []

        def fetcher():
            calls.append(1)
            return ["a", "b"]

        r1 = await cached_autocomplete(("test", 1), fetcher)
        r2 = await cached_autocomplete(("test", 1), fetcher)

        assert r1 == ["a", "b"]
        assert r2 == ["a", "b"]
        assert len(calls) == 1  # fetcher called only once

    @pytest.mark.asyncio
    async def test_different_keys_produce_separate_entries(self):
        from utils.cache import cached_autocomplete

        r1 = await cached_autocomplete(("test", 1), lambda: ["x"])
        r2 = await cached_autocomplete(("test", 2), lambda: ["y"])

        assert r1 == ["x"]
        assert r2 == ["y"]

    @pytest.mark.asyncio
    async def test_fetcher_error_returns_empty_list(self):
        from utils.cache import cached_autocomplete

        def bad_fetcher():
            raise RuntimeError("DB down")

        result = await cached_autocomplete(("test", 99), bad_fetcher)
        assert result == []

    @pytest.mark.asyncio
    async def test_fetcher_error_does_not_cache(self):
        from utils.cache import cached_autocomplete

        calls = []

        def flaky_fetcher():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("first call fails")
            return ["ok"]

        await cached_autocomplete(("test", 42), flaky_fetcher)  # miss + error
        result = await cached_autocomplete(("test", 42), flaky_fetcher)  # should retry

        assert result == ["ok"]
        assert len(calls) == 2

    def test_invalidate_evicts_key(self):
        from utils.cache import _autocomplete_cache, invalidate_autocomplete

        _autocomplete_cache[("test", 5)] = ["cached"]
        invalidate_autocomplete(("test", 5))

        assert ("test", 5) not in _autocomplete_cache

    def test_invalidate_nonexistent_is_safe(self):
        from utils.cache import invalidate_autocomplete

        invalidate_autocomplete(("test", 999))  # must not raise


# ── build_name_choices ────────────────────────────────────────────────────────


class TestBuildNameChoices:
    def test_empty_current_returns_all(self):
        names = ["Alpha", "Beta", "Gamma"]
        choices = build_name_choices(names, "")
        assert [c.name for c in choices] == ["Alpha", "Beta", "Gamma"]
        assert [c.value for c in choices] == ["Alpha", "Beta", "Gamma"]

    def test_filters_case_insensitively(self):
        names = ["Alpha", "ALPHA", "Beta"]
        choices = build_name_choices(names, "alpha")
        assert len(choices) == 2
        assert all("alpha" in c.name.lower() for c in choices)

    def test_returns_at_most_25(self):
        names = [f"Item {i}" for i in range(30)]
        choices = build_name_choices(names, "")
        assert len(choices) == 25

    def test_truncates_long_names_to_100_chars(self):
        long_name = "x" * 150
        choices = build_name_choices([long_name], "")
        assert len(choices[0].name) == 100
        assert len(choices[0].value) == 100
