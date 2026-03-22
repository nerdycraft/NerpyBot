"""Valkey (Redis-compatible) client for caching and pub/sub."""

from __future__ import annotations

import json
import logging
from typing import Any

import valkey

_log = logging.getLogger(__name__)

# Permissions cache TTL (independent of JWT expiry) — short enough that guild
# removals/role changes are reflected within this window without requiring re-login.
PERM_CACHE_TTL = 15 * 60  # 15 minutes


class ValkeyClient:
    """Wrapper around Valkey operations with namespaced keys."""

    PREFIX = "nerpybot"

    def __init__(self, client: Any, blocking_client: Any | None = None):
        """Initialize with a Valkey (or fake) client instance.

        blocking_client, if provided, is used exclusively for blpop.  It must
        have socket_timeout=None so the TCP read does not expire before the
        server-side blpop timeout fires.
        """
        self._client = client
        self._blocking_client = blocking_client if blocking_client is not None else client

    @classmethod
    def create(cls, url: str) -> ValkeyClient:
        """Connect to a real Valkey instance."""
        client = valkey.from_url(url, decode_responses=True)
        # Blocking commands (blpop) need socket_timeout=None: the server holds
        # the connection open for up to `timeout` seconds, and a shorter client-
        # side socket timeout fires first, raising "Timeout reading from socket".
        blocking_client = valkey.from_url(url, decode_responses=True, socket_timeout=None)
        return cls(client, blocking_client)

    @classmethod
    def create_fake(cls) -> ValkeyClient:
        """Create a dict-backed fake for testing."""
        fake = _FakeValkeyClient()
        return cls(fake, fake)

    def _key(self, *parts: str) -> str:
        """Build a namespaced Valkey key from the given parts."""
        return ":".join([self.PREFIX, *parts])

    # ── Permission cache ──

    def set_permissions(self, user_id: str, perms: dict, ttl: int) -> None:
        """Cache guild permission dict for a user with a TTL (in seconds)."""
        key = self._key("user", user_id, "perms")
        self._client.set(key, json.dumps(perms), ex=ttl)

    def get_permissions(self, user_id: str) -> dict | None:
        """Return cached guild permissions for a user, or None if expired/absent."""
        key = self._key("user", user_id, "perms")
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    # ── Discord token cache ──

    def set_discord_token(self, user_id: str, token: str, ttl: int) -> None:
        """Cache the Discord OAuth2 access token for a user with a TTL (in seconds)."""
        key = self._key("user", user_id, "token")
        self._client.set(key, token, ex=ttl)

    def get_discord_token(self, user_id: str) -> str | None:
        """Return the cached Discord OAuth2 access token, or None if absent/expired."""
        key = self._key("user", user_id, "token")
        return self._client.get(key)

    # ── OAuth state (CSRF) ──

    def set_oauth_state(self, state: str, ttl: int = 300) -> None:
        """Store a short-lived OAuth state token for CSRF verification."""
        key = self._key("oauth", "state", state)
        self._client.set(key, "1", ex=ttl)

    def pop_oauth_state(self, state: str) -> bool:
        """Consume an OAuth state token atomically. Returns True if valid, False if absent/expired."""
        key = self._key("oauth", "state", state)
        return self._client.getdel(key) is not None

    # ── Cleanup ──

    def delete_user_cache(self, user_id: str) -> None:
        """Delete all cached data for a user (permissions + token)."""
        self._client.delete(
            self._key("user", user_id, "perms"),
            self._key("user", user_id, "token"),
        )

    # ── Pub/Sub for bot commands ──

    async def send_bot_command(self, command: str, payload: dict, timeout: float = 3.0) -> dict | None:
        """Publish a command and wait for a reply. Returns None on timeout."""
        import asyncio
        import uuid

        request_id = str(uuid.uuid4())
        reply_channel = self._key("reply", request_id)
        cmd_channel = self._key("cmd")

        message = json.dumps({"request_id": request_id, "command": command, **payload})
        self._client.publish(cmd_channel, message)

        # Use the dedicated blocking client so socket_timeout=None does not
        # interfere with the regular client's fast KV operations.
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._blocking_client.blpop, reply_channel, timeout=max(1, int(timeout))),
                timeout=timeout + 1,
            )
            if result:
                _, data = result
                return json.loads(data)
        except asyncio.TimeoutError:
            pass  # expected — no reply within timeout window
        except Exception as exc:
            _log.warning("Unexpected error waiting for bot command reply: %s", exc)
        return None

    def notify_bot(self, command: str, payload: dict) -> None:
        """Publish a fire-and-forget command to the bot (no reply expected).

        Failures are logged as errors — callers must not rely on delivery.
        """
        try:
            message = json.dumps({"command": command, **payload})
            self._client.publish(self._key("cmd"), message)
        except Exception as exc:
            _log.error("notify_bot: failed to publish %r: %s", command, exc, exc_info=True)

    def push_reply(self, request_id: str, data: dict) -> None:
        """Push a reply to a waiting command (used by bot side)."""
        key = self._key("reply", request_id)
        self._client.lpush(key, json.dumps(data))
        self._client.expire(key, 10)

    def close(self) -> None:
        """Close the underlying Valkey connections if supported."""
        if hasattr(self._client, "close"):
            self._client.close()
        if self._blocking_client is not self._client and hasattr(self._blocking_client, "close"):
            self._blocking_client.close()


class _FakeValkeyClient:
    """Minimal dict-backed Valkey fake for unit tests."""

    def __init__(self):
        """Initialize the fake client with an empty in-memory store."""
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store a value (TTL ignored in fake)."""
        self._store[key] = value

    def get(self, key: str) -> str | None:
        """Return a stored value or None if absent."""
        return self._store.get(key)

    def delete(self, *keys: str) -> None:
        """Remove one or more keys from the store."""
        for key in keys:
            self._store.pop(key, None)

    def publish(self, channel: str, message: str) -> None:
        """No-op — pub/sub is not simulated in the fake."""
        pass  # no-op in fake

    def lpush(self, key: str, value: str) -> None:
        """Push a value to a list key (fake stores only the last value)."""
        self._store[key] = value

    def blpop(self, key: str, timeout: int = 0) -> tuple[str, str] | None:
        """Pop and return a list item, or None if the key is absent."""
        val = self._store.pop(key, None)
        if val is not None:
            return (key, val)
        return None

    def expire(self, key: str, seconds: int) -> None:
        """No-op — expiry is not simulated in the fake."""
        pass  # no-op in fake

    def getdel(self, key: str) -> str | None:
        """Atomically get and delete a key. Returns the value or None if absent."""
        return self._store.pop(key, None)
