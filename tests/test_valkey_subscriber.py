from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBotCommandHandler:
    def test_health_command_returns_stats(self, mock_bot):
        """The health command handler returns bot metrics."""
        from bot import handle_valkey_command

        mock_bot.guilds = [MagicMock(), MagicMock()]
        mock_bot.latency = 0.045
        mock_bot.voice_clients = [MagicMock()]
        mock_bot.uptime = datetime.now(UTC) - timedelta(hours=1)
        mock_bot.extensions = {"modules.admin": MagicMock(), "modules.music": MagicMock()}

        result = handle_valkey_command(mock_bot, "health", {})
        assert result["guild_count"] == 2
        assert result["voice_connections"] == 1
        assert "latency_ms" in result
        assert "uptime_seconds" in result
        assert "python_version" in result
        assert "discord_py_version" in result
        assert "bot_version" in result

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
        assert "Unknown command" in result["error"]

    def test_module_load_success(self, mock_bot):
        """module_load command should load an extension."""
        from bot import handle_valkey_command

        mock_bot.loop = MagicMock()
        mock_bot.load_extension = AsyncMock()

        with patch("bot.run_coroutine_threadsafe") as mock_run:
            future = MagicMock()
            future.result = MagicMock(return_value=None)
            mock_run.return_value = future

            result = handle_valkey_command(mock_bot, "module_load", {"module": "wow"})
            assert result["success"] is True
            mock_run.assert_called_once()

    def test_module_load_invalid_name(self, mock_bot):
        """module_load should reject invalid module names."""
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "module_load", {"module": "invalid-name"})
        assert result["success"] is False
        assert "Invalid module name" in result["error"]

    def test_module_load_with_uppercase_rejected(self, mock_bot):
        """module_load should reject module names with uppercase letters."""
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "module_load", {"module": "WowModule"})
        assert result["success"] is False
        assert "Invalid module name" in result["error"]

    def test_module_load_failure(self, mock_bot):
        """module_load should return error on exception."""
        from bot import handle_valkey_command

        mock_bot.loop = MagicMock()

        with patch("bot.run_coroutine_threadsafe") as mock_run:
            future = MagicMock()
            future.result = MagicMock(side_effect=Exception("Module not found"))
            mock_run.return_value = future

            result = handle_valkey_command(mock_bot, "module_load", {"module": "missing"})
            assert result["success"] is False
            assert "Module not found" in result["error"]

    def test_module_unload_success(self, mock_bot):
        """module_unload command should unload an extension."""
        from bot import handle_valkey_command

        mock_bot.loop = MagicMock()
        mock_bot.unload_extension = AsyncMock()

        with patch("bot.run_coroutine_threadsafe") as mock_run:
            future = MagicMock()
            future.result = MagicMock(return_value=None)
            mock_run.return_value = future

            result = handle_valkey_command(mock_bot, "module_unload", {"module": "music"})
            assert result["success"] is True

    def test_module_unload_invalid_name(self, mock_bot):
        """module_unload should reject invalid module names."""
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "module_unload", {"module": ""})
        assert result["success"] is False
        assert "Invalid module name" in result["error"]

    def test_get_channels_returns_channel_list(self, mock_bot):
        """get_channels should return list of channels in guild."""
        from bot import handle_valkey_command

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_channel1 = MagicMock()
        mock_channel1.id = 111
        mock_channel1.name = "general"
        mock_channel1.type = MagicMock(value=0)
        mock_channel2 = MagicMock()
        mock_channel2.id = 222
        mock_channel2.name = "voice"
        mock_channel2.type = MagicMock(value=2)
        mock_guild.channels = [mock_channel1, mock_channel2]
        mock_bot.get_guild = MagicMock(return_value=mock_guild)

        result = handle_valkey_command(mock_bot, "get_channels", {"guild_id": "12345"})
        assert len(result["channels"]) == 2
        assert result["channels"][0]["name"] == "general"

    def test_get_channels_nonexistent_guild(self, mock_bot):
        """get_channels should return empty list for nonexistent guild."""
        from bot import handle_valkey_command

        mock_bot.get_guild = MagicMock(return_value=None)

        result = handle_valkey_command(mock_bot, "get_channels", {"guild_id": "99999"})
        assert result["channels"] == []

    def test_get_roles_returns_role_list(self, mock_bot):
        """get_roles should return list of roles in guild."""
        from bot import handle_valkey_command

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_role1 = MagicMock()
        mock_role1.id = 111
        mock_role1.name = "Admin"
        mock_role1.position = 10
        mock_role1.is_default = MagicMock(return_value=False)
        mock_role2 = MagicMock()
        mock_role2.id = 222
        mock_role2.name = "@everyone"
        mock_role2.position = 0
        mock_role2.is_default = MagicMock(return_value=True)
        mock_guild.roles = [mock_role1, mock_role2]
        mock_bot.get_guild = MagicMock(return_value=mock_guild)

        result = handle_valkey_command(mock_bot, "get_roles", {"guild_id": "12345"})
        assert len(result["roles"]) == 1
        assert result["roles"][0]["name"] == "Admin"

    def test_get_roles_nonexistent_guild(self, mock_bot):
        """get_roles should return empty list for nonexistent guild."""
        from bot import handle_valkey_command

        mock_bot.get_guild = MagicMock(return_value=None)

        result = handle_valkey_command(mock_bot, "get_roles", {"guild_id": "99999"})
        assert result["roles"] == []

    def test_get_member_names_returns_names(self, mock_bot):
        """get_member_names should return display names for user IDs."""
        from bot import handle_valkey_command

        mock_guild = MagicMock()
        mock_guild.id = 12345
        mock_member1 = MagicMock()
        mock_member1.display_name = "Alice"
        mock_member2 = MagicMock()
        mock_member2.display_name = "Bob"
        mock_guild.get_member = MagicMock(side_effect=lambda uid: mock_member1 if uid == 111 else mock_member2 if uid == 222 else None)
        mock_bot.get_guild = MagicMock(return_value=mock_guild)

        result = handle_valkey_command(mock_bot, "get_member_names", {"guild_id": "12345", "user_ids": ["111", "222", "999"]})
        assert result["111"] == "Alice"
        assert result["222"] == "Bob"
        assert "999" not in result

    def test_get_member_names_nonexistent_guild(self, mock_bot):
        """get_member_names should return empty dict for nonexistent guild."""
        from bot import handle_valkey_command

        mock_bot.get_guild = MagicMock(return_value=None)

        result = handle_valkey_command(mock_bot, "get_member_names", {"guild_id": "99999", "user_ids": ["111"]})
        assert result == {}

    def test_post_apply_button_queues_task(self, mock_bot):
        """post_apply_button should queue a task to post the button."""
        from bot import handle_valkey_command

        mock_bot.loop = MagicMock()

        with patch("bot.run_coroutine_threadsafe") as mock_run:
            result = handle_valkey_command(mock_bot, "post_apply_button", {"form_id": "123"})
            assert result["queued"] is True
            mock_run.assert_called_once()

    def test_post_apply_button_missing_form_id(self, mock_bot):
        """post_apply_button should return error if form_id is missing."""
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "post_apply_button", {})
        assert "error" in result
        assert "form_id required" in result["error"]

    def test_search_realms_returns_matches(self, mock_bot):
        """search_realms should return matching realm names."""
        from bot import handle_valkey_command

        wow_cog = MagicMock()
        wow_cog._realm_cache = {
            "eu-silvermoon": {"region": "eu", "name": "Silvermoon", "slug": "silvermoon"},
            "eu-argent-dawn": {"region": "eu", "name": "Argent Dawn", "slug": "argent-dawn"},
            "us-stormrage": {"region": "us", "name": "Stormrage", "slug": "stormrage"},
        }
        wow_cog._ensure_realm_cache = AsyncMock()
        mock_bot.cogs = {"WorldofWarcraft": wow_cog}

        with patch("bot.run_coroutine_threadsafe") as mock_run:
            future = MagicMock()
            future.result = MagicMock(return_value=None)
            mock_run.return_value = future

            result = handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "silver"})
            assert len(result["realms"]) == 1
            assert result["realms"][0]["name"] == "Silvermoon"

    def test_search_realms_query_too_short(self, mock_bot):
        """search_realms should return empty list for queries < 2 chars."""
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "a"})
        assert result["realms"] == []

    def test_search_realms_wow_module_not_loaded(self, mock_bot):
        """search_realms should return error if WoW module not loaded."""
        from bot import handle_valkey_command

        mock_bot.cogs = {}

        result = handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "silver"})
        assert result["realms"] == []
        assert "error" in result

    def test_validate_wow_guild_valid(self, mock_bot):
        """validate_wow_guild should validate guild exists."""
        from bot import handle_valkey_command

        wow_cog = MagicMock()
        api_mock = MagicMock()
        api_mock.guild_roster = MagicMock(return_value={"guild": {"name": "TestGuild"}})
        wow_cog._get_retailclient = MagicMock(return_value=api_mock)
        mock_bot.cogs = {"WorldofWarcraft": wow_cog}

        result = handle_valkey_command(mock_bot, "validate_wow_guild", {
            "region": "eu",
            "realm_slug": "silvermoon",
            "guild_name": "test-guild"
        })
        assert result["valid"] is True
        assert result["display_name"] == "TestGuild"

    def test_validate_wow_guild_not_found(self, mock_bot):
        """validate_wow_guild should return False for non-existent guild."""
        from bot import handle_valkey_command

        wow_cog = MagicMock()
        api_mock = MagicMock()
        api_mock.guild_roster = MagicMock(return_value={"code": 404})
        wow_cog._get_retailclient = MagicMock(return_value=api_mock)
        mock_bot.cogs = {"WorldofWarcraft": wow_cog}

        result = handle_valkey_command(mock_bot, "validate_wow_guild", {
            "region": "eu",
            "realm_slug": "silvermoon",
            "guild_name": "nonexistent"
        })
        assert result["valid"] is False
        assert result["display_name"] is None

    def test_validate_wow_guild_rate_limited(self, mock_bot):
        """validate_wow_guild should handle rate limiting."""
        from bot import handle_valkey_command

        wow_cog = MagicMock()
        api_mock = MagicMock()
        api_mock.guild_roster = MagicMock(return_value={"code": 429})
        wow_cog._get_retailclient = MagicMock(return_value=api_mock)
        mock_bot.cogs = {"WorldofWarcraft": wow_cog}

        result = handle_valkey_command(mock_bot, "validate_wow_guild", {
            "region": "eu",
            "realm_slug": "silvermoon",
            "guild_name": "test"
        })
        assert result["valid"] is False
        assert "rate limited" in result["error"]

    def test_validate_wow_guild_missing_params(self, mock_bot):
        """validate_wow_guild should return False for missing params."""
        from bot import handle_valkey_command

        result = handle_valkey_command(mock_bot, "validate_wow_guild", {"region": "eu"})
        assert result["valid"] is False

    def test_validate_wow_guild_wow_module_not_loaded(self, mock_bot):
        """validate_wow_guild should return error if WoW module not loaded."""
        from bot import handle_valkey_command

        mock_bot.cogs = {}

        result = handle_valkey_command(mock_bot, "validate_wow_guild", {
            "region": "eu",
            "realm_slug": "silvermoon",
            "guild_name": "test"
        })
        assert result["valid"] is False
        assert "error" in result