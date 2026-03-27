# web/twitch.py
"""Twitch Helix API client for EventSub management."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

_log = logging.getLogger(__name__)

_TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
_TWITCH_API_BASE = "https://api.twitch.tv/helix"


class TwitchClient:
    """Async Twitch Helix API client using httpx."""

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._http = httpx.AsyncClient()

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def get_app_access_token(self) -> str:
        """Return a valid client credentials access token, refreshing if expired."""
        now = time.monotonic()
        if self._token and now < self._token_expires_at - 60:
            return self._token
        resp = await self._http.post(
            _TWITCH_AUTH_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires_at = now + data.get("expires_in", 3600)
        _log.debug("Refreshed Twitch app access token (expires in %ss)", data.get("expires_in", 3600))
        return self._token

    async def _headers(self) -> dict[str, str]:
        token = await self.get_app_access_token()
        return {"Client-Id": self._client_id, "Authorization": f"Bearer {token}"}

    async def get_users(self, logins: list[str]) -> list[dict[str, Any]]:
        """Resolve Twitch login names to user objects with id and display_name."""
        if not logins:
            return []
        headers = await self._headers()
        results = []
        for i in range(0, len(logins), 100):
            chunk = logins[i : i + 100]
            resp = await self._http.get(
                f"{_TWITCH_API_BASE}/users",
                headers=headers,
                params=[("login", login) for login in chunk],
            )
            resp.raise_for_status()
            results.extend(resp.json().get("data", []))
        return results

    async def create_eventsub_subscription(
        self,
        event_type: str,
        broadcaster_id: str,
        callback_url: str,
        secret: str,
    ) -> dict[str, Any]:
        """Register an EventSub subscription. Returns the subscription object."""
        payload = {
            "type": event_type,
            "version": "1",
            "condition": {"broadcaster_user_id": broadcaster_id},
            "transport": {
                "method": "webhook",
                "callback": callback_url,
                "secret": secret,
            },
        }
        resp = await self._http.post(
            f"{_TWITCH_API_BASE}/eventsub/subscriptions",
            json=payload,
            headers=await self._headers(),
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return data[0] if data else {}

    async def delete_eventsub_subscription(self, subscription_id: str) -> None:
        """Delete an EventSub subscription by Twitch's UUID."""
        resp = await self._http.delete(
            f"{_TWITCH_API_BASE}/eventsub/subscriptions",
            params={"id": subscription_id},
            headers=await self._headers(),
        )
        if resp.status_code not in (204, 404):
            resp.raise_for_status()

    async def list_eventsub_subscriptions(self) -> list[dict[str, Any]]:
        """List all active EventSub subscriptions for this app."""
        results = []
        cursor = None
        while True:
            params: dict[str, Any] = {"first": 100}
            if cursor:
                params["after"] = cursor
            resp = await self._http.get(
                f"{_TWITCH_API_BASE}/eventsub/subscriptions",
                params=params,
                headers=await self._headers(),
            )
            resp.raise_for_status()
            body = resp.json()
            results.extend(body.get("data", []))
            cursor = body.get("pagination", {}).get("cursor")
            if not cursor:
                break
        return results

    @staticmethod
    def verify_signature(
        secret: str,
        message_id: str,
        timestamp: str,
        body: bytes,
        signature_header: str,
    ) -> bool:
        """Verify the HMAC-SHA256 signature from Twitch.

        Twitch signs: HMAC-SHA256(secret, message_id + timestamp + raw_body)
        and sends it as 'sha256=<hex>' in the Twitch-Eventsub-Message-Signature header.
        """
        if not signature_header.startswith("sha256="):
            return False
        expected_hex = signature_header[7:]
        raw = (message_id + timestamp).encode() + body
        computed = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, expected_hex)
