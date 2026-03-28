# tests/web/test_twitch_client.py
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch


class TestTwitchClientSignature:
    def test_verify_valid_signature(self):
        from web.twitch import TwitchClient

        secret = "mysecret"
        msg_id = "abc123"
        timestamp = "2024-01-01T00:00:00Z"
        body = b'{"event":"test"}'
        raw = (msg_id + timestamp).encode() + body
        sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        assert TwitchClient.verify_signature(secret, msg_id, timestamp, body, sig) is True

    def test_reject_invalid_signature(self):
        from web.twitch import TwitchClient

        assert TwitchClient.verify_signature("secret", "id", "ts", b"body", "sha256=badhash") is False

    def test_reject_wrong_prefix(self):
        from web.twitch import TwitchClient

        secret = "s"
        raw = ("id" + "ts").encode() + b"body"
        sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()  # no sha256= prefix
        assert TwitchClient.verify_signature(secret, "id", "ts", b"body", sig) is False


class TestTwitchClientTokenCache:
    async def test_get_app_access_token_caches(self):
        from web.twitch import TwitchClient

        client = TwitchClient("client_id", "client_secret")
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"access_token": "tok123", "expires_in": 3600}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            token1 = await client.get_app_access_token()
            token2 = await client.get_app_access_token()
        assert token1 == "tok123"
        assert token2 == "tok123"
        assert mock_post.call_count == 1  # cached — only one HTTP call

    async def test_token_refresh_when_expired(self):
        """Token within 60s of expiry triggers a new HTTP call."""
        from web.twitch import TwitchClient
        import time

        client = TwitchClient("client_id", "client_secret")
        client._token = "old_token"
        client._token_expires_at = time.monotonic() + 30  # within 60s buffer — needs refresh
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"access_token": "new_token", "expires_in": 3600}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            token = await client.get_app_access_token()
        assert token == "new_token"


class TestTwitchClientDeleteIdempotency:
    async def test_delete_404_is_ok(self):
        """Deleting an already-deleted subscription (404) should not raise."""
        from web.twitch import TwitchClient
        import time

        client = TwitchClient("client_id", "client_secret")
        # Mock token
        client._token = "tok"
        client._token_expires_at = time.monotonic() + 7200

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=mock_response):
            # Should not raise
            await client.delete_eventsub_subscription("sub-uuid-123")
