class TestValkeyHelpers:
    """Test Valkey helper functions with a dict-based fake."""

    def test_permission_cache_roundtrip(self):
        from web.cache import ValkeyClient

        client = ValkeyClient.create_fake()
        perms = {
            "987654321": {"level": "admin", "name": "Guild A", "icon": None},
            "111222333": {"level": "mod", "name": "Guild B", "icon": "abc123"},
        }
        client.set_permissions("123", perms, ttl=300)
        result = client.get_permissions("123")
        assert result == perms

    def test_permission_cache_miss_returns_none(self):
        from web.cache import ValkeyClient

        client = ValkeyClient.create_fake()
        assert client.get_permissions("nonexistent") is None

    def test_discord_token_roundtrip(self):
        from web.cache import ValkeyClient

        client = ValkeyClient.create_fake()
        client.set_discord_token("123", "discord_access_token", ttl=3600)
        assert client.get_discord_token("123") == "discord_access_token"

    def test_discord_token_miss_returns_none(self):
        from web.cache import ValkeyClient

        client = ValkeyClient.create_fake()
        assert client.get_discord_token("nonexistent") is None

    def test_delete_user_cache(self):
        from web.cache import ValkeyClient

        client = ValkeyClient.create_fake()
        client.set_permissions("123", {"guild": "admin"}, ttl=300)
        client.set_discord_token("123", "tok", ttl=300)
        client.delete_user_cache("123")
        assert client.get_permissions("123") is None
        assert client.get_discord_token("123") is None


class TestTwitchDedup:
    def test_mark_and_check_seen(self):
        from web.cache import ValkeyClient

        vk = ValkeyClient.create_fake()
        assert vk.is_twitch_event_seen("msg-abc") is False
        vk.mark_twitch_event_seen("msg-abc", ttl=300)
        assert vk.is_twitch_event_seen("msg-abc") is True

    def test_not_seen_for_different_id(self):
        from web.cache import ValkeyClient

        vk = ValkeyClient.create_fake()
        vk.mark_twitch_event_seen("msg-abc", ttl=300)
        assert vk.is_twitch_event_seen("msg-xyz") is False

    def test_nx_first_caller_wins(self):
        """SET NX — second mark call is a no-op."""
        from web.cache import ValkeyClient

        vk = ValkeyClient.create_fake()
        vk.mark_twitch_event_seen("msg-abc", ttl=300)
        vk.mark_twitch_event_seen("msg-abc", ttl=300)  # second call should be no-op
        assert vk.is_twitch_event_seen("msg-abc") is True
