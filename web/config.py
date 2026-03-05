"""Web dashboard configuration — reads from NERPYBOT_* environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value


@dataclass(frozen=True)
class WebConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    jwt_secret: str
    jwt_expiry_hours: int
    valkey_url: str
    ops: list[int]
    db_connection_string: str

    @classmethod
    def from_env(cls) -> WebConfig:
        client_id = _require_env("NERPYBOT_CLIENT_ID")
        client_secret = _require_env("NERPYBOT_WEB_CLIENT_SECRET")
        jwt_secret = _require_env("NERPYBOT_WEB_JWT_SECRET")

        ops_raw = _require_env("NERPYBOT_OPS")
        ops = [int(o.strip()) for o in ops_raw.split(",") if o.strip()]

        redirect_uri = os.environ.get("NERPYBOT_WEB_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
        jwt_expiry_hours = int(os.environ.get("NERPYBOT_WEB_JWT_EXPIRY_HOURS", "24"))
        valkey_url = os.environ.get("NERPYBOT_WEB_VALKEY_URL", "valkey://localhost:6379")
        db_connection_string = _build_db_connection_string()

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            jwt_secret=jwt_secret,
            jwt_expiry_hours=jwt_expiry_hours,
            valkey_url=valkey_url,
            ops=ops,
            db_connection_string=db_connection_string,
        )


def _build_db_connection_string() -> str:
    """Build SQLAlchemy connection string from NERPYBOT_DB_* env vars.

    Mirrors the logic in NerdyPy/bot.py NerpyBot.build_connection_string().
    """
    db_type = os.environ.get("NERPYBOT_DB_TYPE", "sqlite")
    db_name = os.environ.get("NERPYBOT_DB_NAME", "db.db")

    if "postgresql" in db_type:
        db_type = f"{db_type}+psycopg"

    db_username = os.environ.get("NERPYBOT_DB_USERNAME", "")
    db_password = os.environ.get("NERPYBOT_DB_PASSWORD", "")
    db_host = os.environ.get("NERPYBOT_DB_HOST", "")
    db_port = os.environ.get("NERPYBOT_DB_PORT", "")

    if not db_username and not db_host:
        return f"{db_type}:///{db_name}"

    auth = db_username
    if db_password:
        auth += f":{db_password}"
    if db_host:
        auth += f"@{db_host}"
    if db_port:
        auth += f":{db_port}"

    return f"{db_type}://{auth}/{db_name}"
