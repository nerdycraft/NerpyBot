"""FastAPI dependency injection stubs and auth dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from web.config import WebConfig
    from web.cache import ValkeyClient

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
    user_id = int(user["sub"])
    if user_id in config.ops:
        return user
    from models.admin import PremiumUser

    if not PremiumUser.has(user_id, session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Premium access required")
    return user


def require_guild_access(
    guild_id: int,
    user: dict = Depends(get_current_user),
    config: WebConfig = Depends(get_config),
    vk: ValkeyClient = Depends(get_valkey),
) -> dict:
    """Require the user has admin/mod access to the given guild. Operators bypass."""
    user_id = int(user["sub"])
    if user_id in config.ops:
        return user

    perms = vk.get_permissions(user["sub"])
    if perms is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No guild permissions found — re-login")

    guild_str = str(guild_id)
    entry = perms.get(guild_str)
    level = entry["level"] if isinstance(entry, dict) else None
    if level not in ("admin", "mod"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient guild permissions")

    user["guild_permission"] = level
    return user
