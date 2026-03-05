"""Auth routes — login, callback, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from web.auth.jwt import create_access_token
from web.auth.oauth2 import build_authorize_url, exchange_code, fetch_discord_user, fetch_user_guilds
from web.auth.permissions import resolve_guild_permissions
from web.config import WebConfig
from web.dependencies import get_config, get_current_user, get_valkey
from web.schemas import GuildSummary, TokenResponse, UserInfo
from web.valkey import ValkeyClient

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(config: WebConfig = Depends(get_config)):
    """Redirect to Discord OAuth2 authorization."""
    url = build_authorize_url(config.client_id, config.redirect_uri)
    return RedirectResponse(url=url, status_code=307)


@router.get("/callback", response_model=TokenResponse)
async def callback(
    code: str = Query(None),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Handle Discord OAuth2 callback."""
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")

    token_data = await exchange_code(code, config.client_id, config.client_secret, config.redirect_uri)
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 604800)

    user_data = await fetch_discord_user(access_token)
    guilds = await fetch_user_guilds(access_token)

    user_id = user_data["id"]
    username = user_data.get("username", "Unknown")

    # Cache permissions and Discord token in Valkey
    perms = resolve_guild_permissions(guilds)
    vk.set_permissions(user_id, perms, ttl=300)
    vk.set_discord_token(user_id, access_token, ttl=expires_in)

    jwt = create_access_token(
        user_id=user_id,
        username=username,
        secret=config.jwt_secret,
        expiry_hours=config.jwt_expiry_hours,
    )

    return TokenResponse(access_token=jwt)


@router.get("/me", response_model=UserInfo)
async def me(
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
):
    """Return the current user's profile and accessible guilds."""
    user_id = user["sub"]
    perms = vk.get_permissions(user_id)

    guilds = []
    if perms:
        for guild_id, level in perms.items():
            guilds.append(GuildSummary(id=guild_id, name="", icon=None, permission_level=level))

    return UserInfo(
        id=user_id,
        username=user["username"],
        is_operator=int(user_id) in config.ops,
        guilds=guilds,
    )
