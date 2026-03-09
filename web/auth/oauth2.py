"""Discord OAuth2 helpers."""

from __future__ import annotations

import httpx
from urllib.parse import urlencode

DISCORD_API = "https://discord.com/api/v10"
DISCORD_OAUTH2_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = f"{DISCORD_API}/oauth2/token"


def build_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Build the Discord OAuth2 authorization URL with a CSRF state token."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
    }
    return f"{DISCORD_OAUTH2_URL}?{urlencode(params)}"


async def exchange_code(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange an authorization code for an access token."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.post(
            DISCORD_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_discord_user(access_token: str) -> dict:
    """Fetch the authenticated user's profile."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_user_guilds(access_token: str) -> list[dict]:
    """Fetch the guilds the user is a member of."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()
