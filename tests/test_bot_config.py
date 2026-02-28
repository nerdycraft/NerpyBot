# -*- coding: utf-8 -*-
"""Tests for parse_env_config(), deep_merge(), and parse_config() in bot.py."""

from NerdyPy.bot import parse_env_config, deep_merge, parse_config


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        assert deep_merge(base, override) == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"wow": {"wow_id": "old_id", "guild_news": {"track_mounts": True}}}
        override = {"wow": {"guild_news": {"track_mounts": False}}}
        result = deep_merge(base, override)
        assert result == {"wow": {"wow_id": "old_id", "guild_news": {"track_mounts": False}}}

    def test_base_is_not_mutated(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        deep_merge(base, override)
        assert base == {"a": {"b": 1}}

    def test_override_replaces_non_dict_with_dict(self):
        base = {"key": "string"}
        override = {"key": {"nested": True}}
        assert deep_merge(base, override) == {"key": {"nested": True}}

    def test_empty_override(self):
        base = {"a": 1}
        assert deep_merge(base, {}) == {"a": 1}

    def test_empty_base(self):
        override = {"a": 1}
        assert deep_merge({}, override) == {"a": 1}


class TestParseEnvConfig:
    def test_empty_when_no_vars_set(self, monkeypatch):
        for key in [
            "NERPYBOT_TOKEN",
            "NERPYBOT_CLIENT_ID",
            "NERPYBOT_OPS",
            "NERPYBOT_MODULES",
            "NERPYBOT_DB_TYPE",
            "NERPYBOT_DB_NAME",
            "NERPYBOT_DB_USERNAME",
            "NERPYBOT_DB_PASSWORD",
            "NERPYBOT_DB_HOST",
            "NERPYBOT_DB_PORT",
            "NERPYBOT_AUDIO_BUFFER_LIMIT",
            "NERPYBOT_YOUTUBE_KEY",
            "NERPYBOT_RIOT_KEY",
            "NERPYBOT_WOW_CLIENT_ID",
            "NERPYBOT_WOW_CLIENT_SECRET",
            "NERPYBOT_WOW_POLL_INTERVAL_MINUTES",
            "NERPYBOT_WOW_MOUNT_BATCH_SIZE",
            "NERPYBOT_WOW_TRACK_MOUNTS",
            "NERPYBOT_WOW_ACTIVE_DAYS",
            "NERPYBOT_ERROR_RECIPIENTS",
        ]:
            monkeypatch.delenv(key, raising=False)
        assert parse_env_config() == {}

    def test_token(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_TOKEN", "my_token")
        result = parse_env_config()
        assert result["bot"]["token"] == "my_token"

    def test_client_id(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_CLIENT_ID", "111222333")
        result = parse_env_config()
        assert result["bot"]["client_id"] == "111222333"

    def test_ops_comma_separated(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_OPS", "111, 222, 333")
        result = parse_env_config()
        assert result["bot"]["ops"] == ["111", "222", "333"]

    def test_modules_comma_separated(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_MODULES", "wow,league,music")
        result = parse_env_config()
        assert result["bot"]["modules"] == ["wow", "league", "music"]

    def test_db_type(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_DB_TYPE", "sqlite")
        result = parse_env_config()
        assert result["database"]["db_type"] == "sqlite"

    def test_db_name(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_DB_NAME", "/data/db.db")
        result = parse_env_config()
        assert result["database"]["db_name"] == "/data/db.db"

    def test_db_credentials(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_DB_USERNAME", "admin")
        monkeypatch.setenv("NERPYBOT_DB_PASSWORD", "s3cr3t")
        monkeypatch.setenv("NERPYBOT_DB_HOST", "db.host")
        monkeypatch.setenv("NERPYBOT_DB_PORT", "5432")
        result = parse_env_config()
        assert result["database"]["db_username"] == "admin"
        assert result["database"]["db_password"] == "s3cr3t"
        assert result["database"]["db_host"] == "db.host"
        assert result["database"]["db_port"] == "5432"

    def test_audio_buffer_limit_as_int(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_AUDIO_BUFFER_LIMIT", "10")
        result = parse_env_config()
        assert result["audio"]["buffer_limit"] == 10

    def test_youtube_key(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_YOUTUBE_KEY", "yt_key_abc")
        result = parse_env_config()
        assert result["music"]["ytkey"] == "yt_key_abc"

    def test_riot_key(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_RIOT_KEY", "riot_key_abc")
        result = parse_env_config()
        assert result["league"]["riot"] == "riot_key_abc"

    def test_wow_credentials(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_WOW_CLIENT_ID", "wow_id")
        monkeypatch.setenv("NERPYBOT_WOW_CLIENT_SECRET", "wow_secret")
        result = parse_env_config()
        assert result["wow"]["wow_id"] == "wow_id"
        assert result["wow"]["wow_secret"] == "wow_secret"

    def test_wow_guild_news_nested(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_WOW_POLL_INTERVAL_MINUTES", "30")
        monkeypatch.setenv("NERPYBOT_WOW_MOUNT_BATCH_SIZE", "50")
        monkeypatch.setenv("NERPYBOT_WOW_ACTIVE_DAYS", "14")
        result = parse_env_config()
        gn = result["wow"]["guild_news"]
        assert gn["poll_interval_minutes"] == 30
        assert gn["mount_batch_size"] == 50
        assert gn["active_days"] == 14

    def test_wow_track_mounts_true(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_WOW_TRACK_MOUNTS", "true")
        assert parse_env_config()["wow"]["guild_news"]["track_mounts"] is True

    def test_wow_track_mounts_false(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_WOW_TRACK_MOUNTS", "false")
        assert parse_env_config()["wow"]["guild_news"]["track_mounts"] is False

    def test_wow_track_mounts_yes(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_WOW_TRACK_MOUNTS", "yes")
        assert parse_env_config()["wow"]["guild_news"]["track_mounts"] is True

    def test_error_recipients_comma_separated(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_ERROR_RECIPIENTS", "111,222")
        result = parse_env_config()
        assert result["notifications"]["error_recipients"] == ["111", "222"]

    def test_only_set_vars_appear_in_result(self, monkeypatch):
        monkeypatch.setenv("NERPYBOT_TOKEN", "tok")
        monkeypatch.delenv("NERPYBOT_CLIENT_ID", raising=False)
        result = parse_env_config()
        assert "token" in result["bot"]
        assert "client_id" not in result["bot"]


class TestParseConfig:
    def test_env_overrides_yaml(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("bot:\n  token: yaml_token\n  client_id: '123'\n")
        monkeypatch.setenv("NERPYBOT_TOKEN", "env_token")
        result = parse_config(config_file)
        assert result["bot"]["token"] == "env_token"
        assert result["bot"]["client_id"] == "123"

    def test_yaml_preserved_when_no_env(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("bot:\n  token: yaml_token\n")
        monkeypatch.delenv("NERPYBOT_TOKEN", raising=False)
        result = parse_config(config_file)
        assert result["bot"]["token"] == "yaml_token"

    def test_missing_yaml_returns_env_only(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NERPYBOT_TOKEN", "env_only_token")
        result = parse_config(tmp_path / "nonexistent.yaml")
        assert result["bot"]["token"] == "env_only_token"

    def test_no_yaml_no_env_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.delenv("NERPYBOT_TOKEN", raising=False)
        result = parse_config(tmp_path / "nonexistent.yaml")
        assert result == {}
