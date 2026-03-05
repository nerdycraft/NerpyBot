class TestValkeyHelpers:
    """Test Valkey helper functions with a dict-based fake."""

    def test_permission_cache_roundtrip(self):
        from web.valkey import ValkeyClient

        client = ValkeyClient.create_fake()
        perms = {"987654321": "admin", "111222333": "mod"}
        client.set_permissions("123", perms, ttl=300)
        result = client.get_permissions("123")
        assert result == perms

    def test_permission_cache_miss_returns_none(self):
        from web.valkey import ValkeyClient

        client = ValkeyClient.create_fake()
        assert client.get_permissions("nonexistent") is None

    def test_discord_token_roundtrip(self):
        from web.valkey import ValkeyClient

        client = ValkeyClient.create_fake()
        client.set_discord_token("123", "discord_access_token", ttl=3600)
        assert client.get_discord_token("123") == "discord_access_token"

    def test_discord_token_miss_returns_none(self):
        from web.valkey import ValkeyClient

        client = ValkeyClient.create_fake()
        assert client.get_discord_token("nonexistent") is None

    def test_delete_user_cache(self):
        from web.valkey import ValkeyClient

        client = ValkeyClient.create_fake()
        client.set_permissions("123", {"guild": "admin"}, ttl=300)
        client.set_discord_token("123", "tok", ttl=300)
        client.delete_user_cache("123")
        assert client.get_permissions("123") is None
        assert client.get_discord_token("123") is None
