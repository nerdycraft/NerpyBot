"""
Configuration loading for NerpyBot.

Merges a YAML config file with ``NERPYBOT_*`` environment variables.
Environment variables take priority over the file when both are present.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import yaml

_LOG = logging.getLogger(__name__)


def _csv(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def _to_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes")


def _set_nested(d: dict, keys: list[str], value) -> None:
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def parse_env_config() -> dict:
    """Read NERPYBOT_* environment variables and return a config dict."""
    env: dict = {}
    mappings = [
        ("NERPYBOT_TOKEN", ["bot", "token"], str),
        ("NERPYBOT_CLIENT_ID", ["bot", "client_id"], str),
        ("NERPYBOT_OPS", ["bot", "ops"], _csv),
        ("NERPYBOT_MODULES", ["bot", "modules"], _csv),
        ("NERPYBOT_DB_TYPE", ["database", "db_type"], str),
        ("NERPYBOT_DB_NAME", ["database", "db_name"], str),
        ("NERPYBOT_DB_USERNAME", ["database", "db_username"], str),
        ("NERPYBOT_DB_PASSWORD", ["database", "db_password"], str),
        ("NERPYBOT_DB_HOST", ["database", "db_host"], str),
        ("NERPYBOT_DB_PORT", ["database", "db_port"], str),
        ("NERPYBOT_AUDIO_BUFFER_LIMIT", ["audio", "buffer_limit"], int),
        ("NERPYBOT_YOUTUBE_KEY", ["music", "ytkey"], str),
        ("NERPYBOT_RIOT_KEY", ["league", "riot"], str),
        ("NERPYBOT_WOW_CLIENT_ID", ["wow", "wow_id"], str),
        ("NERPYBOT_WOW_CLIENT_SECRET", ["wow", "wow_secret"], str),
        ("NERPYBOT_WOW_POLL_INTERVAL_MINUTES", ["wow", "guild_news", "poll_interval_minutes"], int),
        ("NERPYBOT_WOW_MOUNT_BATCH_SIZE", ["wow", "guild_news", "mount_batch_size"], int),
        ("NERPYBOT_WOW_TRACK_MOUNTS", ["wow", "guild_news", "track_mounts"], _to_bool),
        ("NERPYBOT_WOW_ACTIVE_DAYS", ["wow", "guild_news", "active_days"], int),
        ("NERPYBOT_ERROR_RECIPIENTS", ["notifications", "error_recipients"], _csv),
        ("NERPYBOT_VALKEY_URL", ["web", "valkey_url"], str),
        ("NERPYBOT_WEB_VALKEY_URL", ["web", "valkey_url"], str),  # overrides NERPYBOT_VALKEY_URL if both are set
        ("NERPYBOT_LOG_LEVEL", ["bot", "log_level"], str),
    ]
    for var_name, keys, converter in mappings:
        value = os.environ.get(var_name)
        if value:
            _set_nested(env, keys, converter(value))
    return env


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base; override wins on conflicts."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def parse_config(config_path: Optional[Path] = None) -> dict:
    config = {}
    path = config_path or Path("./config.yaml")
    if path.exists():
        with open(path) as stream:
            try:
                config = yaml.safe_load(stream) or {}
            except yaml.YAMLError as exc:
                _LOG.error("Error in configuration file: %s", exc)
    return deep_merge(config, parse_env_config())
