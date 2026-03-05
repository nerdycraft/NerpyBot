"""Valkey (Redis-compatible) client for caching and pub/sub."""

from __future__ import annotations

import json
from typing import Any


class ValkeyClient:
    """Wrapper around Valkey operations with namespaced keys."""

    PREFIX = "nerpybot"

    def __init__(self, client: Any):
        self._client = client

    @classmethod
    def create(cls, url: str) -> ValkeyClient:
        """Connect to a real Valkey instance."""
        import valkey

        client = valkey.from_url(url, decode_responses=True)
        return cls(client)

    @classmethod
    def create_fake(cls) -> ValkeyClient:
        """Create a dict-backed fake for testing."""
        return cls(_FakeValkeyClient())

    def _key(self, *parts: str) -> str:
        return ":".join([self.PREFIX, *parts])

    # ── Permission cache ──

    def set_permissions(self, user_id: str, perms: dict, ttl: int) -> None:
        key = self._key("user", user_id, "perms")
        self._client.set(key, json.dumps(perms), ex=ttl)

    def get_permissions(self, user_id: str) -> dict | None:
        key = self._key("user", user_id, "perms")
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    # ── Discord token cache ──

    def set_discord_token(self, user_id: str, token: str, ttl: int) -> None:
        key = self._key("user", user_id, "token")
        self._client.set(key, token, ex=ttl)

    def get_discord_token(self, user_id: str) -> str | None:
        key = self._key("user", user_id, "token")
        return self._client.get(key)

    # ── Cleanup ──

    def delete_user_cache(self, user_id: str) -> None:
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
                asyncio.to_thread(self._client.blpop, reply_channel, timeout=int(timeout)),
                timeout=timeout + 1,
            )
            if result:
                _, data = result
                return json.loads(data)
        except (asyncio.TimeoutError, Exception):
            pass
        return None

    def push_reply(self, request_id: str, data: dict) -> None:
        """Push a reply to a waiting command (used by bot side)."""
        key = self._key("reply", request_id)
        self._client.lpush(key, json.dumps(data))
        self._client.expire(key, 10)

    def close(self) -> None:
        if hasattr(self._client, "close"):
            self._client.close()


class _FakeValkeyClient:
    """Minimal dict-backed Valkey fake for unit tests."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    def publish(self, channel: str, message: str) -> None:
        pass  # no-op in fake

    def lpush(self, key: str, value: str) -> None:
        self._store[key] = value

    def blpop(self, key: str, timeout: int = 0) -> tuple[str, str] | None:
        val = self._store.pop(key, None)
        if val is not None:
            return (key, val)
        return None

    def expire(self, key: str, seconds: int) -> None:
        pass  # no-op in fake
