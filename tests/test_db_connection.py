# -*- coding: utf-8 -*-
"""Tests for NerpyBot.build_connection_string."""

from sqlalchemy.engine.url import make_url

from NerdyPy.bot import NerpyBot


class TestBuildConnectionString:
    """Verify connection string building for SQLite and PostgreSQL."""

    def test_sqlite_fallback_when_no_database_config(self):
        config = {}
        result = NerpyBot.build_connection_string(config)
        assert result == "sqlite:///db.db"

    def test_sqlite_has_no_charset(self):
        config = {}
        result = NerpyBot.build_connection_string(config)
        assert "charset" not in result

    def test_postgresql_has_no_charset(self):
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "pass",
                "db_host": "localhost",
                "db_port": "5432",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert "charset" not in result
        assert result.startswith("postgresql+psycopg://")

    def test_postgresql_connection_string_format(self):
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "pass",
                "db_host": "localhost",
                "db_port": "5432",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg://user:pass@localhost:5432/nerpybot"

    def test_minimal_postgresql_config(self):
        """PostgreSQL with only required fields."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg:///nerpybot"

    def test_postgresql_with_username_only(self):
        """PostgreSQL with username but no password."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "dbuser",
            }
        }
        parsed = make_url(NerpyBot.build_connection_string(config))
        assert parsed.username == "dbuser"
        assert parsed.database == "nerpybot"
        assert parsed.password is None
        assert parsed.host is None

    def test_postgresql_with_host_no_port(self):
        """PostgreSQL with host but no port."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "pass",
                "db_host": "dbserver",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "postgresql+psycopg://user:pass@dbserver/nerpybot"

    def test_postgresql_with_port_no_host(self):
        """PostgreSQL with port but no host: username and database must be recoverable."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "pass",
                "db_port": "5432",
            }
        }
        parsed = make_url(NerpyBot.build_connection_string(config))
        assert parsed.username == "user"
        assert parsed.database == "nerpybot"

    def test_postgresql_with_empty_password(self):
        """Empty password string should be treated as no password."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "",
            }
        }
        parsed = make_url(NerpyBot.build_connection_string(config))
        assert parsed.username == "user"
        assert parsed.database == "nerpybot"
        assert parsed.password is None

    def test_sqlite_explicit_config(self):
        """SQLite with explicit config."""
        config = {
            "database": {
                "db_type": "sqlite",
                "db_name": "/data/custom.db",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "sqlite:////data/custom.db"

    def test_postgresql_driver_variant(self):
        """PostgreSQL type should get +psycopg driver appended."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert "+psycopg" in result
        assert result.startswith("postgresql+psycopg://")

    def test_connection_string_special_characters_in_password(self):
        """Password with special characters: host and database must be recoverable."""
        config = {
            "database": {
                "db_type": "postgresql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "p@ss:w0rd!",
                "db_host": "localhost",
            }
        }
        parsed = make_url(NerpyBot.build_connection_string(config))
        assert parsed.username == "user"
        assert parsed.host == "localhost"
        assert parsed.database == "nerpybot"
