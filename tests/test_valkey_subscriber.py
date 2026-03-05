import json
from unittest.mock import MagicMock, patch

import pytest


class TestBotCommandHandler:
    def test_health_command_returns_stats(self, mock_bot):
        """The health command handler returns bot metrics."""
        from bot import handle_valkey_command

        mock_bot.guilds = [MagicMock(), MagicMock()]
        mock_bot.latency = 0.045
        mock_bot.voice_clients = [MagicMock()]
        mock_bot.uptime = MagicMock()
        mock_bot.uptime.timestamp = MagicMock(return_value=1000)
        mock_bot.extensions = {"modules.admin": MagicMock(), "modules.music": MagicMock()}

        result = handle_valkey_command(mock_bot, "health", {})
        assert result["guild_count"] == 2
        assert result["voice_connections"] == 1
        assert "latency_ms" in result

    def test_list_modules_command(self, mock_bot):
        from bot import handle_valkey_command

        mock_bot.extensions = {"modules.admin": MagicMock(), "modules.music": MagicMock()}

        result = handle_valkey_command(mock_bot, "list_modules", {})
        assert len(result["modules"]) == 2
        names = [m["name"] for m in result["modules"]]
        assert "admin" in names
        assert "music" in names

    def test_unknown_command_returns_error(self, mock_bot):
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "unknown_cmd", {})
        assert "error" in result
