import os
from unittest.mock import patch

import pytest


class TestWebConfig:
    def test_from_env_minimal(self):
        """Config loads from NERPYBOT_* env vars."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_CLIENT_ID": "123456",
            "NERPYBOT_OPS": "111,222",
            "NERPYBOT_WEB_CLIENT_SECRET": "secret123",
            "NERPYBOT_WEB_JWT_SECRET": "jwtsecret",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = WebConfig.from_env()

        assert cfg.client_id == "123456"
        assert cfg.ops == [111, 222]
        assert cfg.client_secret == "secret123"
        assert cfg.jwt_secret == "jwtsecret"
        assert cfg.jwt_expiry_hours == 24  # default
        assert cfg.valkey_url == "valkey://localhost:6379"  # default
        assert "callback" in cfg.redirect_uri  # default

    def test_from_env_all_overrides(self):
        """All env vars override defaults."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_CLIENT_ID": "999",
            "NERPYBOT_OPS": "42",
            "NERPYBOT_WEB_CLIENT_SECRET": "s",
            "NERPYBOT_WEB_JWT_SECRET": "j",
            "NERPYBOT_WEB_JWT_EXPIRY_HOURS": "48",
            "NERPYBOT_WEB_VALKEY_URL": "valkey://redis:6380/1",
            "NERPYBOT_WEB_REDIRECT_URI": "https://example.com/cb",
            "NERPYBOT_DB_TYPE": "postgresql",
            "NERPYBOT_DB_NAME": "mydb",
            "NERPYBOT_DB_USERNAME": "user",
            "NERPYBOT_DB_PASSWORD": "pass",
            "NERPYBOT_DB_HOST": "dbhost",
            "NERPYBOT_DB_PORT": "5432",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = WebConfig.from_env()

        assert cfg.jwt_expiry_hours == 48
        assert cfg.valkey_url == "valkey://redis:6380/1"
        assert cfg.redirect_uri == "https://example.com/cb"
        assert "postgresql+psycopg" in cfg.db_connection_string
        assert "mydb" in cfg.db_connection_string

    def test_from_env_missing_required_raises(self):
        """Missing required env vars raise ValueError."""
        from web.config import WebConfig

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="NERPYBOT_CLIENT_ID"):
                WebConfig.from_env()

    def test_db_connection_string_sqlite_default(self):
        """Default DB is SQLite."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_CLIENT_ID": "123",
            "NERPYBOT_OPS": "1",
            "NERPYBOT_WEB_CLIENT_SECRET": "s",
            "NERPYBOT_WEB_JWT_SECRET": "j",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = WebConfig.from_env()

        assert cfg.db_connection_string == "sqlite:///db.db"
