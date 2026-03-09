"""Auth routes — login, callback, me."""

from __future__ import annotations

import logging

import httpx

_log = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from models.admin import BotGuild
from web.auth.jwt import create_access_token
from web.auth.oauth2 import build_authorize_url, exchange_code, fetch_discord_user, fetch_user_guilds
from web.auth.permissions import resolve_guild_permissions
from web.config import WebConfig
from web.dependencies import get_config, get_current_user, get_db_session, get_valkey
from web.schemas import GuildSummary, UserInfo
from web.cache import ValkeyClient

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(config: WebConfig = Depends(get_config)):
    """Redirect to Discord OAuth2 authorization."""
    url = build_authorize_url(config.client_id, config.redirect_uri)
    _log.debug("login: redirecting to Discord OAuth, redirect_uri=%s", config.redirect_uri)
    return RedirectResponse(url=url, status_code=307)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Handle Discord OAuth2 callback."""
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
    _log.debug("callback: authenticated user_id=%s username=%s guilds=%d", user_id, username, len(guilds))

    # Cache permissions and Discord token in Valkey
    perms = resolve_guild_permissions(guilds)
    vk.set_permissions(user_id, perms, ttl=config.jwt_expiry_hours * 3600)
    vk.set_discord_token(user_id, access_token, ttl=expires_in)
    _log.debug("callback: cached permissions for %d guilds", len(perms))

    jwt = create_access_token(
        user_id=user_id,
        username=username,
        secret=config.jwt_secret,
        expiry_hours=config.jwt_expiry_hours,
    )

    base = config.frontend_url.rstrip("/")
    redirect_target = f"{base}/?token=<redacted>"
    _log.debug("callback: redirecting to %s", redirect_target)
    redirect_target = f"{base}/?token={jwt}"
    return RedirectResponse(url=redirect_target, status_code=302)


@router.get("/me", response_model=UserInfo)
async def me(
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
    session=Depends(get_db_session),
):
    """Return the current user's profile and accessible guilds."""
    user_id = user["sub"]
    perms = vk.get_permissions(user_id)
    bot_guilds = BotGuild.get_ids(session)
    _log.debug("/me: bot_guilds from DB has %d entries", len(bot_guilds))

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

    return UserInfo(
        id=user_id,
        username=user["username"],
        is_operator=int(user_id) in config.ops,
        guilds=guilds,
    )
