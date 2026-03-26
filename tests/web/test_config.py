import os
from unittest.mock import patch

import pytest


class TestWebConfigFromEnv:
    def test_from_env_with_web_prefix(self):
        """Config loads from NERPYBOT_WEB_* env vars (canonical names)."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_WEB_CLIENT_ID": "123456",
            "NERPYBOT_WEB_OPS": "111,222",
            "NERPYBOT_WEB_CLIENT_SECRET": "secret123",
            "NERPYBOT_WEB_JWT_SECRET": "jwtsecret",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.from_env()

        assert cfg.client_id == "123456"
        assert cfg.ops == [111, 222]
        assert cfg.client_secret == "secret123"
        assert cfg.jwt_secret == "jwtsecret"
        assert cfg.jwt_expiry_hours == 24  # default
        assert cfg.valkey_url == "valkey://localhost:6379"  # default
        assert "callback" in cfg.redirect_uri  # default

    def test_from_env_unprefixed_fallback(self):
        """Unprefixed NERPYBOT_* vars work as fallback for shared values."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_CLIENT_ID": "fallback_id",
            "NERPYBOT_OPS": "42",
            "NERPYBOT_WEB_CLIENT_SECRET": "s",
            "NERPYBOT_WEB_JWT_SECRET": "j",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.from_env()

        assert cfg.client_id == "fallback_id"
        assert cfg.ops == [42]

    def test_web_prefix_takes_priority_over_unprefixed(self):
        """NERPYBOT_WEB_* wins over NERPYBOT_* when both are set."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_CLIENT_ID": "old_id",
            "NERPYBOT_WEB_CLIENT_ID": "web_id",
            "NERPYBOT_OPS": "1",
            "NERPYBOT_WEB_OPS": "2",
            "NERPYBOT_WEB_CLIENT_SECRET": "s",
            "NERPYBOT_WEB_JWT_SECRET": "j",
            "NERPYBOT_DB_TYPE": "sqlite",
            "NERPYBOT_WEB_DB_TYPE": "postgresql",
            "NERPYBOT_WEB_DB_NAME": "webdb",
            "NERPYBOT_WEB_DB_USERNAME": "u",
            "NERPYBOT_WEB_DB_HOST": "h",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.from_env()

        assert cfg.client_id == "web_id"
        assert cfg.ops == [2]
        assert "postgresql+psycopg" in cfg.db_connection_string

    def test_from_env_all_overrides(self):
        """All NERPYBOT_WEB_* env vars override defaults."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_WEB_CLIENT_ID": "999",
            "NERPYBOT_WEB_OPS": "42",
            "NERPYBOT_WEB_CLIENT_SECRET": "s",
            "NERPYBOT_WEB_JWT_SECRET": "j",
            "NERPYBOT_WEB_JWT_EXPIRY_HOURS": "48",
            "NERPYBOT_WEB_VALKEY_URL": "valkey://redis:6380/1",
            "NERPYBOT_WEB_REDIRECT_URI": "https://example.com/cb",
            "NERPYBOT_WEB_DB_TYPE": "postgresql",
            "NERPYBOT_WEB_DB_NAME": "mydb",
            "NERPYBOT_WEB_DB_USERNAME": "user",
            "NERPYBOT_WEB_DB_PASSWORD": "pass",
            "NERPYBOT_WEB_DB_HOST": "dbhost",
            "NERPYBOT_WEB_DB_PORT": "5432",
        }
        with patch.dict(os.environ, env, clear=True):
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
            with pytest.raises(ValueError, match="CLIENT_ID"):
                WebConfig.from_env()

    def test_db_connection_string_sqlite_default(self):
        """Default DB is SQLite."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_WEB_CLIENT_ID": "123",
            "NERPYBOT_WEB_OPS": "1",
            "NERPYBOT_WEB_CLIENT_SECRET": "s",
            "NERPYBOT_WEB_JWT_SECRET": "j",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.from_env()

        assert cfg.db_connection_string == "sqlite:///db.db"


class TestWebConfigFromFile:
    def test_load_from_config_file(self, tmp_path):
        """Config loads values from a YAML config file."""
        from web.config import WebConfig

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "bot:\n"
            '  client_id: "file_client_id"\n'
            "  ops:\n"
            '    - "111"\n'
            '    - "222"\n'
            "web:\n"
            "  client_secret: file_secret\n"
            "  jwt_secret: file_jwt\n"
            "  valkey_url: valkey://filehost:6379\n"
            "database:\n"
            "  db_type: sqlite\n"
            "  db_name: test.db\n"
        )

        with patch.dict(os.environ, {}, clear=True):
            cfg = WebConfig.load(config_file)

        assert cfg.client_id == "file_client_id"
        assert cfg.ops == [111, 222]
        assert cfg.client_secret == "file_secret"
        assert cfg.jwt_secret == "file_jwt"
        assert cfg.valkey_url == "valkey://filehost:6379"
        assert cfg.db_connection_string == "sqlite:///test.db"

    def test_env_vars_override_file(self, tmp_path):
        """Env vars take priority over config file values."""
        from web.config import WebConfig

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "bot:\n"
            '  client_id: "from_file"\n'
            "  ops:\n"
            '    - "100"\n'
            "web:\n"
            "  client_secret: from_file\n"
            "  jwt_secret: from_file\n"
            "  valkey_url: valkey://from-file:6379\n"
        )

        env = {"NERPYBOT_WEB_CLIENT_ID": "from_env", "NERPYBOT_WEB_VALKEY_URL": "valkey://from-env:6380"}
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.load(config_file)

        assert cfg.client_id == "from_env"  # env wins
        assert cfg.valkey_url == "valkey://from-env:6380"  # env wins
        assert cfg.client_secret == "from_file"  # file provides
        assert cfg.ops == [100]  # file provides

    def test_missing_file_falls_back_to_env(self, tmp_path):
        """If config file doesn't exist, env vars are used."""
        from web.config import WebConfig

        env = {
            "NERPYBOT_WEB_CLIENT_ID": "env_id",
            "NERPYBOT_WEB_OPS": "42",
            "NERPYBOT_WEB_CLIENT_SECRET": "env_secret",
            "NERPYBOT_WEB_JWT_SECRET": "env_jwt",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.load(tmp_path / "nonexistent.yaml")

        assert cfg.client_id == "env_id"
        assert cfg.ops == [42]

    def test_load_missing_required_from_both_raises(self, tmp_path):
        """Missing required values from both file and env raise ValueError."""
        from web.config import WebConfig

        config_file = tmp_path / "config.yaml"
        config_file.write_text("bot:\n  client_id: test\n")

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="client_secret"):
                WebConfig.load(config_file)


class TestWebConfigFrontendUrl:
    _base_env = {
        "NERPYBOT_WEB_CLIENT_ID": "123",
        "NERPYBOT_WEB_OPS": "1",
        "NERPYBOT_WEB_CLIENT_SECRET": "s",
        "NERPYBOT_WEB_JWT_SECRET": "j",
    }

    def test_frontend_url_defaults_to_slash(self):
        from web.config import WebConfig

        with patch.dict(os.environ, self._base_env, clear=True):
            cfg = WebConfig.from_env()
        assert cfg.frontend_url == "/"

    def test_frontend_url_from_env(self):
        from web.config import WebConfig

        env = {**self._base_env, "NERPYBOT_WEB_FRONTEND_URL": "http://localhost:5173"}
        with patch.dict(os.environ, env, clear=True):
            cfg = WebConfig.from_env()
        assert cfg.frontend_url == "http://localhost:5173"


def test_twitch_defaults():
    from web.config import WebConfig

    cfg = WebConfig(
        client_id="x",
        client_secret="x",
        redirect_uri="x",
        jwt_secret="x",
        jwt_expiry_hours=1,
        valkey_url="x",
        ops=[1],
        db_connection_string="sqlite:///:memory:",
    )
    assert cfg.twitch_client_id == ""
    assert cfg.twitch_client_secret == ""
    assert cfg.twitch_webhook_url == ""
    assert cfg.twitch_webhook_secret == ""


def test_twitch_env_vars(monkeypatch):
    """Twitch config fields are loaded from env vars through WebConfig.from_env()."""
    from web.config import WebConfig

    env = {
        "NERPYBOT_WEB_CLIENT_ID": "123",
        "NERPYBOT_WEB_OPS": "1",
        "NERPYBOT_WEB_CLIENT_SECRET": "s",
        "NERPYBOT_WEB_JWT_SECRET": "j",
        "NERPYBOT_WEB_TWITCH_CLIENT_ID": "t_id",
        "NERPYBOT_WEB_TWITCH_CLIENT_SECRET": "t_sec",
        "NERPYBOT_WEB_TWITCH_WEBHOOK_URL": "https://example.com/webhooks/twitch",
        "NERPYBOT_WEB_TWITCH_WEBHOOK_SECRET": "t_wh_sec",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    cfg = WebConfig.from_env()

    assert cfg.twitch_client_id == "t_id"
    assert cfg.twitch_client_secret == "t_sec"
    assert cfg.twitch_webhook_url == "https://example.com/webhooks/twitch"
    assert cfg.twitch_webhook_secret == "t_wh_sec"
