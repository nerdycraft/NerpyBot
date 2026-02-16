# -*- coding: utf-8 -*-
"""Tests for NerpyBot.build_connection_string."""

from NerdyPy.NerdyPy import NerpyBot


class TestBuildConnectionString:
    """Verify connection string building with correct charset handling."""

    def test_sqlite_fallback_when_no_database_config(self):
        config = {}
        result = NerpyBot.build_connection_string(config)
        assert result == "sqlite:///db.db"

    def test_sqlite_has_no_charset(self):
        config = {}
        result = NerpyBot.build_connection_string(config)
        assert "charset" not in result

    def test_mysql_includes_charset_utf8mb4(self):
        config = {
            "database": {
                "db_type": "mysql",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "pass",
                "db_host": "localhost",
                "db_port": "3306",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert "charset=utf8mb4" in result
        assert result.startswith("mysql+pymysql://")

    def test_mariadb_includes_charset_utf8mb4(self):
        config = {
            "database": {
                "db_type": "mariadb",
                "db_name": "nerpybot",
                "db_username": "user",
                "db_password": "pass",
                "db_host": "localhost",
                "db_port": "3306",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert "charset=utf8mb4" in result
        assert result.startswith("mariadb+pymysql://")

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
        assert result.startswith("postgresql://")

    def test_mysql_connection_string_format(self):
        config = {
            "database": {
                "db_type": "mysql",
                "db_name": "testdb",
                "db_username": "admin",
                "db_password": "secret",
                "db_host": "db.example.com",
                "db_port": "3306",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert result == "mysql+pymysql://admin:secret@db.example.com:3306/testdb?charset=utf8mb4"

    def test_minimal_mysql_config(self):
        """MySQL with only required fields still gets charset."""
        config = {
            "database": {
                "db_type": "mysql",
                "db_name": "nerpybot",
            }
        }
        result = NerpyBot.build_connection_string(config)
        assert "charset=utf8mb4" in result
        assert result == "mysql+pymysql:///nerpybot?charset=utf8mb4"
