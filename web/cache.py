"""Valkey (Redis-compatible) client for caching and pub/sub."""

from __future__ import annotations

import json
import logging
from typing import Any

import valkey

_log = logging.getLogger(__name__)


class ValkeyClient:
    """Wrapper around Valkey operations with namespaced keys."""

    PREFIX = "nerpybot"

    def __init__(self, client: Any):
        """Initialize with a Valkey (or fake) client instance."""
        self._client = client

    @classmethod
    def create(cls, url: str) -> ValkeyClient:
        """Connect to a real Valkey instance."""
        client = valkey.from_url(url, decode_responses=True)
        return cls(client)

    @classmethod
    def create_fake(cls) -> ValkeyClient:
        """Create a dict-backed fake for testing."""
        return cls(_FakeValkeyClient())

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

        # Poll for reply (simple approach — real implementation would use async subscribe)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self._client.blpop, reply_channel, timeout=max(1, int(timeout))),
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

    def push_reply(self, request_id: str, data: dict) -> None:
        """Push a reply to a waiting command (used by bot side)."""
        key = self._key("reply", request_id)
        self._client.lpush(key, json.dumps(data))
        self._client.expire(key, 10)

    # ── Bot guild presence ──

    def set_bot_guilds(self, guild_ids: set[str]) -> None:
        """Replace the full set of guild IDs where the bot is present."""
        key = self._key("bot", "guilds")
        self._client.delete(key)
        if guild_ids:
            self._client.sadd(key, *guild_ids)

    def get_bot_guilds(self) -> set[str]:
        """Return the set of guild IDs where the bot is present, or empty set if unknown."""
        key = self._key("bot", "guilds")
        result = self._client.smembers(key)
        return result if result else set()

    def add_bot_guild(self, guild_id: str) -> None:
        """Add a single guild ID to the bot presence set."""
        self._client.sadd(self._key("bot", "guilds"), guild_id)

    def remove_bot_guild(self, guild_id: str) -> None:
        """Remove a single guild ID from the bot presence set."""
        self._client.srem(self._key("bot", "guilds"), guild_id)

    def close(self) -> None:
        """Close the underlying Valkey connection if supported."""
        if hasattr(self._client, "close"):
            self._client.close()


class _FakeValkeyClient:
    """Minimal dict-backed Valkey fake for unit tests."""

    def __init__(self):
        """Initialize the fake client with an empty in-memory store."""
        self._store: dict[str, str] = {}
        self._sets: dict[str, set[str]] = {}

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
            self._sets.pop(key, None)

    def sadd(self, key: str, *members: str) -> None:
        """Add members to a set."""
        self._sets.setdefault(key, set()).update(members)

    def srem(self, key: str, *members: str) -> None:
        """Remove members from a set."""
        if key in self._sets:
            self._sets[key].discard(*members)

    def smembers(self, key: str) -> set[str]:
        """Return all members of a set, or empty set if absent."""
        return set(self._sets.get(key, set()))

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
