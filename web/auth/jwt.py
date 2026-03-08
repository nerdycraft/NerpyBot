"""JWT token creation and validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import jwt

ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    username: str,
    secret: str,
    expiry_hours: int,
) -> str:
    """Create a signed JWT token for the given user.

    Args:
        user_id: Discord user snowflake ID (string).
        username: Discord username for display purposes.
        secret: HMAC secret used to sign the token.
        expiry_hours: Lifetime of the token in hours.

    Returns:
        Encoded JWT string.
    """
    expire = datetime.now(UTC) + timedelta(hours=expiry_hours)
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    """Decode and validate a JWT token. Raises jose.JWTError on failure."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
