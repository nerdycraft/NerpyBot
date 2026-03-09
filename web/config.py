"""Web dashboard configuration — reads from config.yaml and/or NERPYBOT_* env vars.

Follows the same pattern as the bot: config file provides defaults, env vars override.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

import yaml

log = logging.getLogger(__name__)


def _get(sources: list[dict], *keys: str, default: str = "") -> str:
    """Look up a value from a list of dicts (first wins), falling back to default."""
    for src in sources:
        node = src
        for key in keys:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                node = None
                break
        if node is not None and not isinstance(node, dict):
            return str(node).strip()
    return default


def _require(value: str, name: str) -> str:
    """Raise ValueError if value is empty, otherwise return it."""
    if not value:
        raise ValueError(f"Required config value {name!r} is not set (via config file or env var)")
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
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    frontend_url: str = "/"

    @classmethod
    def load(cls, config_path: Path | str | None = None) -> WebConfig:
        """Load config from file + env vars.  Env vars take priority."""
        file_cfg = _load_config_file(config_path)
        return cls._build(file_cfg)

    @classmethod
    def from_env(cls) -> WebConfig:
        """Load config from env vars only (no config file)."""
        return cls._build({})

    @classmethod
    def _build(cls, file_cfg: dict) -> WebConfig:
        """Build a WebConfig by layering env vars over file config over defaults."""
        # Layer: env vars (highest priority) → file config → defaults
        env = _env_to_dict()
        sources = [env, file_cfg]

        client_id = _require(_get(sources, "bot", "client_id"), "bot.client_id / NERPYBOT_WEB_CLIENT_ID")
        client_secret = _require(
            _get(sources, "web", "client_secret"), "web.client_secret / NERPYBOT_WEB_CLIENT_SECRET"
        )
        jwt_secret = _require(_get(sources, "web", "jwt_secret"), "web.jwt_secret / NERPYBOT_WEB_JWT_SECRET")

        ops = _resolve_ops(sources)
        if not ops:
            _require("", "bot.ops / NERPYBOT_WEB_OPS")

        redirect_uri = _get(sources, "web", "redirect_uri", default="http://localhost:8000/api/auth/callback")
        jwt_expiry_hours = int(_get(sources, "web", "jwt_expiry_hours", default="24"))
        valkey_url = _get(sources, "web", "valkey_url", default="valkey://localhost:6379")
        db_connection_string = _build_db_connection_string(sources)

        cors_origins_raw = _get(sources, "web", "cors_origins")
        cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()] if cors_origins_raw else ["*"]
        frontend_url = _get(sources, "web", "frontend_url", default="/")

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            jwt_secret=jwt_secret,
            jwt_expiry_hours=jwt_expiry_hours,
            valkey_url=valkey_url,
            ops=ops,
            db_connection_string=db_connection_string,
            cors_origins=cors_origins,
            frontend_url=frontend_url,
        )


def _resolve_ops(sources: list[dict]) -> list[int]:
    """Resolve ops from sources — handles both YAML lists and CSV strings."""
    for src in sources:
        raw = src.get("bot", {}).get("ops")
        if raw is None:
            continue
        if isinstance(raw, list):
            return [int(o) for o in raw]
        if isinstance(raw, str) and raw.strip():
            return [int(o.strip()) for o in raw.split(",") if o.strip()]
    return []


def _load_config_file(config_path: Path | str | None) -> dict:
    """Load YAML config file, returning {} if not found."""
    path = Path(config_path) if config_path else Path("./config.yaml")
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError:
            log.warning("Failed to parse config file %s — using defaults/env vars", path)
            return {}


def _env_to_dict() -> dict:
    """Map NERPYBOT_WEB_* env vars into a nested dict matching config.yaml structure.

    For shared values (client_id, ops, database) the WEB-prefixed var is checked
    first, falling back to the unprefixed bot var.  This lets the web container use
    its own ``NERPYBOT_WEB_*`` namespace while still working when co-located with
    the bot (sharing ``NERPYBOT_*`` vars).
    """
    cfg: dict = {}
    # (env_vars_to_try, config_key_path) — first env var found wins
    mappings: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
        (("NERPYBOT_WEB_CLIENT_ID", "NERPYBOT_CLIENT_ID"), ("bot", "client_id")),
        (("NERPYBOT_WEB_OPS", "NERPYBOT_OPS"), ("bot", "ops")),
        (("NERPYBOT_WEB_CLIENT_SECRET",), ("web", "client_secret")),
        (("NERPYBOT_WEB_JWT_SECRET",), ("web", "jwt_secret")),
        (("NERPYBOT_WEB_JWT_EXPIRY_HOURS",), ("web", "jwt_expiry_hours")),
        (("NERPYBOT_WEB_VALKEY_URL", "NERPYBOT_VALKEY_URL"), ("web", "valkey_url")),
        (("NERPYBOT_WEB_REDIRECT_URI",), ("web", "redirect_uri")),
        (("NERPYBOT_WEB_CORS_ORIGINS",), ("web", "cors_origins")),
        (("NERPYBOT_WEB_FRONTEND_URL",), ("web", "frontend_url")),
        (("NERPYBOT_WEB_DB_TYPE", "NERPYBOT_DB_TYPE"), ("database", "db_type")),
        (("NERPYBOT_WEB_DB_NAME", "NERPYBOT_DB_NAME"), ("database", "db_name")),
        (("NERPYBOT_WEB_DB_USERNAME", "NERPYBOT_DB_USERNAME"), ("database", "db_username")),
        (("NERPYBOT_WEB_DB_PASSWORD", "NERPYBOT_DB_PASSWORD"), ("database", "db_password")),
        (("NERPYBOT_WEB_DB_HOST", "NERPYBOT_DB_HOST"), ("database", "db_host")),
        (("NERPYBOT_WEB_DB_PORT", "NERPYBOT_DB_PORT"), ("database", "db_port")),
    ]
    for env_vars, keys in mappings:
        value = ""
        for env_var in env_vars:
            value = os.environ.get(env_var, "").strip()
            if value:
                break
        if value:
            node = cfg
            for key in keys[:-1]:
                node = node.setdefault(key, {})
            node[keys[-1]] = value
    return cfg


def _build_db_connection_string(sources: list[dict]) -> str:
    """Build SQLAlchemy connection string from config sources."""
    db_type = _get(sources, "database", "db_type", default="sqlite")
    db_name = _get(sources, "database", "db_name", default="db.db")

    if "postgresql" in db_type and "+psycopg" not in db_type:
        db_type = f"{db_type}+psycopg"

    db_username = _get(sources, "database", "db_username")
    db_password = _get(sources, "database", "db_password")
    db_host = _get(sources, "database", "db_host")
    db_port = _get(sources, "database", "db_port")

    if not db_username and not db_host:
        return f"{db_type}:///{db_name}"

    auth = db_username
    if db_password:
        auth += f":{quote_plus(db_password)}"
    if db_host:
        auth += f"@{db_host}"
        if db_port:
            auth += f":{db_port}"

    return f"{db_type}://{auth}/{db_name}"
