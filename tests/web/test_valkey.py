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
    def test_claim_first_caller_wins(self):
        from web.cache import ValkeyClient

        vk = ValkeyClient.create_fake()
        assert vk.claim_twitch_event("msg-abc", ttl=300) is True
        assert vk.claim_twitch_event("msg-abc", ttl=300) is False

    def test_claim_different_ids_independent(self):
        from web.cache import ValkeyClient

        vk = ValkeyClient.create_fake()
        assert vk.claim_twitch_event("msg-abc", ttl=300) is True
        assert vk.claim_twitch_event("msg-xyz", ttl=300) is True

    def test_claim_returns_false_on_duplicate(self):
        """SET NX — second claim call returns False."""
        from web.cache import ValkeyClient

        vk = ValkeyClient.create_fake()
        first = vk.claim_twitch_event("msg-abc", ttl=300)
        second = vk.claim_twitch_event("msg-abc", ttl=300)
        assert first is True
        assert second is False
