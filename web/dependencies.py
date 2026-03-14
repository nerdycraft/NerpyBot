"""FastAPI dependency injection stubs and auth dependencies."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError as JWTError
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from web.config import WebConfig
    from web.cache import ValkeyClient

_TEST_MODE: bool = bool(os.environ.get("NERPYBOT_TEST_MODE"))
_TEST_USER_ID = "999000000000000000"
_TEST_GUILD_IDS = {"999000000000000001", "999000000000000002", "999000000000000004"}
_TEST_SUPPORT_GUILD_ID = "999000000000000003"


def _is_test_user(user: dict) -> bool:
    return _TEST_MODE and user.get("sub") == _TEST_USER_ID


security = HTTPBearer(auto_error=False)


def get_db_session() -> Session:
    """Placeholder — overridden at app startup."""
    raise NotImplementedError


def get_config() -> WebConfig:
    """Placeholder — overridden at app startup."""
    raise NotImplementedError


def get_valkey() -> ValkeyClient:
    """Placeholder — overridden at app startup."""
    raise NotImplementedError


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    config: WebConfig = Depends(get_config),
) -> dict:
    """Extract and validate the current user from JWT.

    Returns dict with 'sub' (user_id) and 'username'.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    from web.auth.jwt import decode_access_token

    try:
        payload = decode_access_token(credentials.credentials, config.jwt_secret)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    return payload


def require_operator(
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
) -> dict:
    """Require the current user to be a bot operator."""
    if _is_test_user(user):
        return user
    user_id = int(user["sub"])
    if user_id not in config.ops:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operator access required")
    return user


def require_premium(
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
    session: Session = Depends(get_db_session),
) -> dict:
    """Require the current user to have premium access. Operators bypass."""
    if _is_test_user(user):
        return user
    user_id = int(user["sub"])
    if user_id in config.ops:
        return user
    from models.admin import PremiumUser

    if not PremiumUser.has(user_id, session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium access required")
    return user


async def _refresh_guild_perms(vk, user_sub: str, discord_token: str) -> dict:
    """Fetch fresh guild permissions from Discord and write them to the cache.

    Raises HTTPException on network or auth errors so callers can decide
    whether to surface the error or fall back to a degraded mode.
    """
    import httpx

    from web.auth.oauth2 import fetch_user_guilds
    from web.auth.permissions import resolve_guild_permissions
    from web.cache import PERM_CACHE_TTL

    try:
        guilds = await fetch_user_guilds(discord_token)
        perms = resolve_guild_permissions(guilds)
        vk.set_permissions(user_sub, perms, ttl=PERM_CACHE_TTL)
        return perms
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Could not verify guild permissions — please re-login"
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Discord API error")
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not reach Discord")


async def require_guild_access(
    guild_id: int,
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
) -> dict:
    """Require the user has admin/mod access to the given guild. Operators bypass.

    Guild permissions are cached for PERM_CACHE_TTL (15 min). On cache miss the
    dependency attempts a silent refresh via the cached Discord OAuth token so that
    active sessions survive the short TTL without forcing a re-login. If the Discord
    token is also expired the user must re-authenticate to get fresh permissions.
    """
    if _is_test_user(user):
        guild_str = str(guild_id)
        if guild_str == _TEST_SUPPORT_GUILD_ID:
            return {**user, "support_mode": True}
        if guild_str in _TEST_GUILD_IDS:
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient guild permissions")

    user_id = int(user["sub"])
    guild_str = str(guild_id)

    def _has_real_perms(p) -> bool:
        if not p or guild_str not in p:
            return False
        entry = p[guild_str]
        return isinstance(entry, dict) and entry.get("level") in ("admin", "mod")

    if user_id in config.ops:
        perms = vk.get_permissions(user["sub"])
        if not _has_real_perms(perms):
            # Try to refresh from Discord before degrading to support mode
            discord_token = vk.get_discord_token(user["sub"])
            if discord_token is not None:
                try:
                    perms = await _refresh_guild_perms(vk, user["sub"], discord_token)
                except HTTPException:
                    pass  # network/API failure → degrade to support_mode
        if _has_real_perms(perms):
            return user  # real guild permissions — normal access
        return {**user, "support_mode": True}

    perms = vk.get_permissions(user["sub"])
    if perms is None:
        # Try to refresh from Discord using the cached OAuth token
        discord_token = vk.get_discord_token(user["sub"])
        if discord_token is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session expired — please re-login")
        perms = await _refresh_guild_perms(vk, user["sub"], discord_token)

    if not _has_real_perms(perms):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient guild permissions")

    return user
