# -*- coding: utf-8 -*-
"""Tests for NerpyBot.build_connection_string."""

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
