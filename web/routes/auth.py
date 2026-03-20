"""Auth routes — login, callback, me."""

from __future__ import annotations

import logging
import secrets

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from models.admin import BotGuild
from web.auth.jwt import create_access_token
from web.auth.oauth2 import build_authorize_url, exchange_code, fetch_discord_user, fetch_user_guilds
from web.auth.permissions import resolve_guild_permissions
from web.cache import PERM_CACHE_TTL, ValkeyClient
from web.config import WebConfig
from web.dependencies import (
    _TEST_MODE,
    _TEST_USER_ID,
    _get_premium_ids,
    get_config,
    get_current_user,
    get_db_session,
    get_valkey,
)
from web.schemas import GuildSummary, UserInfo

# Cache for the set of bot guild IDs. TTL of 2 minutes; guild join/leave is rare.
_bot_guild_ids_cache: TTLCache = TTLCache(maxsize=1, ttl=120)


def _get_bot_guild_ids(session) -> set[str]:
    """Return the cached set of bot guild ID strings, loading from DB on miss."""
    if "ids" in _bot_guild_ids_cache:
        return _bot_guild_ids_cache["ids"]
    ids = BotGuild.get_ids(session)
    _bot_guild_ids_cache["ids"] = ids
    return ids


_log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
_TEST_GUILDS = [
    GuildSummary(
        id="999000000000000001",
        name="Nerdcraft Central",
        icon=None,
        permission_level="admin",
        bot_present=True,
        invite_url=None,
    ),
    GuildSummary(
        id="999000000000000002",
        name="Quiet Corner",
        icon=None,
        permission_level="mod",
        bot_present=True,
        invite_url=None,
    ),
    GuildSummary(
        id="999000000000000004",
        name="Cool Guild",
        icon=None,
        permission_level="admin",
        bot_present=False,
        invite_url=(
            "https://discord.com/oauth2/authorize"
            "?client_id=0&scope=bot+applications.commands&permissions=0"
            "&guild_id=999000000000000004"
        ),
    ),
]


@router.get("/test-login")
async def test_login(config: WebConfig = Depends(get_config)):
    """Synthetic login for test mode — issues a JWT for the test operator user.

    Only available when NERPYBOT_TEST_MODE is set.  Redirects to the frontend
    the same way the real OAuth callback does, so the frontend token-handling
    code is exercised identically.
    """
    if not _TEST_MODE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    token = create_access_token(
        user_id=_TEST_USER_ID,
        username="TestOperator",
        secret=config.jwt_secret,
        expiry_hours=config.jwt_expiry_hours,
    )
    base = config.frontend_url.rstrip("/")
    return RedirectResponse(url=f"{base}/#token={token}", status_code=302)


@router.get("/login")
async def login(
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Redirect to Discord OAuth2 authorization."""
    state = secrets.token_urlsafe(32)
    vk.set_oauth_state(state, ttl=300)
    url = build_authorize_url(config.client_id, config.redirect_uri, state)
    _log.debug("login: redirecting to Discord OAuth, redirect_uri=%s", config.redirect_uri)
    return RedirectResponse(url=url, status_code=307)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
    session=Depends(get_db_session),
):
    """Handle Discord OAuth2 callback."""
    if not vk.pop_oauth_state(state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")
    try:
        token_data = await exchange_code(code, config.client_id, config.client_secret, config.redirect_uri)
        access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 604800)
        user_data = await fetch_discord_user(access_token)
        guilds = await fetch_user_guilds(access_token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired authorization code"
            )
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Discord rate limit hit — try again shortly"
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Discord API error")
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not reach Discord")

    user_id = user_data["id"]
    username = user_data.get("username", "Unknown")
    _log.debug("callback: authenticated guilds=%d", len(guilds))

    # Cache permissions and Discord token in Valkey
    perms = resolve_guild_permissions(guilds)
    vk.set_permissions(user_id, perms, ttl=PERM_CACHE_TTL)
    vk.set_discord_token(user_id, access_token, ttl=expires_in)
    _log.debug("callback: cached permissions for %d guilds", len(perms))

    jwt = create_access_token(
        user_id=user_id,
        username=username,
        secret=config.jwt_secret,
        expiry_hours=config.jwt_expiry_hours,
    )

    # Use fragment (#token=) instead of query param so the token never appears
    # in server access logs (fragments are not sent in HTTP requests).
    base = config.frontend_url.rstrip("/")
    _log.debug("callback: redirecting to %s/ with token in fragment", base)
    return RedirectResponse(url=f"{base}/#token={jwt}", status_code=302)


@router.get("/me", response_model=UserInfo)
async def me(
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
    session=Depends(get_db_session),
):
    """Return the current user's profile and accessible guilds."""
    user_id = user["sub"]

    if _TEST_MODE and user_id == _TEST_USER_ID:
        return UserInfo(
            id=_TEST_USER_ID,
            username="TestOperator",
            is_operator=True,
            is_premium=True,
            guilds=_TEST_GUILDS,
        )

    perms = vk.get_permissions(user_id)
    if perms is None:
        # Cache miss (TTL expired mid-session) — rehydrate from stored Discord token.
        discord_token = vk.get_discord_token(user_id)
        if not discord_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired — please log in again",
            )
        try:
            guilds = await fetch_user_guilds(discord_token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired — please log in again",
                )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Discord API error")
        except httpx.RequestError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not reach Discord")
        perms = resolve_guild_permissions(guilds)
        vk.set_permissions(user_id, perms, ttl=PERM_CACHE_TTL)
        _log.debug("/me: rehydrated permissions for %d guilds after cache miss", len(perms))
    bot_guilds = _get_bot_guild_ids(session)
    _log.debug("/me: bot_guilds (cached) has %d entries", len(bot_guilds))

    invite_base = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={config.client_id}&scope=bot+applications.commands&permissions=0"
    )

    guilds = []
    if perms:
        for guild_id, entry in perms.items():
            present = guild_id in bot_guilds
            guilds.append(
                GuildSummary(
                    id=guild_id,
                    name=entry["name"],
                    icon=entry.get("icon"),
                    permission_level=entry["level"],
                    bot_present=present,
                    invite_url=None if present else f"{invite_base}&guild_id={guild_id}",
                )
            )

    is_operator = int(user_id) in config.ops
    is_premium = is_operator or int(user_id) in _get_premium_ids(session)

    return UserInfo(
        id=user_id,
        username=user["username"],
        is_operator=is_operator,
        is_premium=is_premium,
        guilds=guilds,
    )
