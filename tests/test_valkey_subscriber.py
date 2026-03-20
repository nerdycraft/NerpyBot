from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.valkey import handle_valkey_command


class TestBotCommandHandler:
    async def test_health_command_returns_stats(self, mock_bot):
        """The health command handler returns bot metrics."""
        mock_bot.guilds = [MagicMock(), MagicMock()]
        mock_bot.latency = 0.045
        mock_bot.voice_clients = []
        mock_bot.uptime = datetime.now(UTC) - timedelta(hours=1)
        mock_bot.extensions = {"modules.admin": MagicMock(), "modules.music": MagicMock()}
        mock_bot.error_counter = MagicMock()
        mock_bot.error_counter.count.return_value = 3

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 5

        @contextmanager
        def _mock_scope():
            yield mock_session

        mock_bot.session_scope = _mock_scope

        mock_proc = MagicMock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024
        with patch("utils.valkey._proc", mock_proc), patch("utils.valkey._cpu_percent_cached", new=2.5):
            result = await handle_valkey_command(mock_bot, "health", {})

        assert result["guild_count"] == 2
        assert result["voice_connections"] == 0
        assert "latency_ms" in result
        assert "uptime_seconds" in result
        assert "python_version" in result
        assert "discord_py_version" in result
        assert "bot_version" in result
        assert result["memory_mb"] == 100.0
        assert result["cpu_percent"] == 2.5
        assert result["error_count_24h"] == 3
        assert result["active_reminders"] == 5
        assert result["voice_details"] == []

    async def test_health_command_with_voice_clients(self, mock_bot, mock_voice_client):
        """Health command includes voice connection details."""
        mock_bot.guilds = []
        mock_bot.latency = 0.01
        mock_bot.voice_clients = [mock_voice_client]
        mock_bot.uptime = datetime.now(UTC) - timedelta(seconds=60)
        mock_bot.extensions = {}
        mock_bot.error_counter = MagicMock()
        mock_bot.error_counter.count.return_value = 0

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        @contextmanager
        def _mock_scope():
            yield mock_session

        mock_bot.session_scope = _mock_scope

        mock_proc = MagicMock()
        mock_proc.memory_info.return_value.rss = 50 * 1024 * 1024
        with patch("utils.valkey._proc", mock_proc), patch("utils.valkey._cpu_percent_cached", new=0.0):
            result = await handle_valkey_command(mock_bot, "health", {})

        assert result["active_reminders"] == 0
        assert len(result["voice_details"]) == 1
        assert result["voice_details"][0]["guild_id"] == "12345"
        assert result["voice_details"][0]["guild_name"] == "Test Guild"
        assert result["voice_details"][0]["channel_name"] == "General Voice"

    async def test_health_command_with_zero_guilds(self, mock_bot):
        """Health command should handle bot in no guilds."""
        mock_bot.guilds = []
        mock_bot.latency = 0.02
        mock_bot.voice_clients = []
        mock_bot.uptime = datetime.now(UTC) - timedelta(seconds=30)
        mock_bot.extensions = {}
        mock_bot.error_counter = MagicMock()
        mock_bot.error_counter.count.return_value = 0

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        @contextmanager
        def _mock_scope():
            yield mock_session

        mock_bot.session_scope = _mock_scope

        mock_proc = MagicMock()
        mock_proc.memory_info.return_value.rss = 50 * 1024 * 1024
        with patch("utils.valkey._proc", mock_proc):
            result = await handle_valkey_command(mock_bot, "health", {})

        assert result["guild_count"] == 0
        assert result["voice_connections"] == 0

    async def test_health_live_command_returns_reduced_payload(self, mock_bot, mock_voice_client):
        """health_live returns the lightweight SSE-facing payload without static fields."""
        mock_bot.latency = 0.03
        mock_bot.voice_clients = [mock_voice_client]
        mock_bot.uptime = datetime.now(UTC) - timedelta(hours=2)

        mock_proc = MagicMock()
        mock_proc.memory_info.return_value.rss = 80 * 1024 * 1024
        with patch("utils.valkey._proc", mock_proc), patch("utils.valkey._cpu_percent_cached", new=5.0):
            result = await handle_valkey_command(mock_bot, "health_live", {})

        assert result["cpu_percent"] == 5.0
        assert result["memory_mb"] == 80.0
        assert result["latency_ms"] == pytest.approx(30.0, abs=1)
        assert result["uptime_seconds"] >= 7200
        assert result["voice_connections"] == 1
        assert isinstance(result["ts"], float)
        assert len(result["voice_details"]) == 1
        detail = result["voice_details"][0]
        assert detail["guild_id"] == "12345"
        assert detail["guild_name"] == "Test Guild"
        assert detail["channel_id"] == "67890"
        assert detail["channel_name"] == "General Voice"
        # Static fields from the full health command must not appear
        assert "guild_count" not in result
        assert "bot_version" not in result
        assert "active_reminders" not in result

    async def test_list_modules_command(self, mock_bot):

        mock_bot.extensions = {"modules.admin": MagicMock(), "modules.music": MagicMock()}

        result = await handle_valkey_command(mock_bot, "list_modules", {})
        assert len(result["modules"]) == 2
        names = [m["name"] for m in result["modules"]]
        assert "admin" in names
        assert "music" in names

    async def test_list_modules_empty(self, mock_bot):
        """List modules should handle no loaded modules."""

        mock_bot.extensions = {}

        result = await handle_valkey_command(mock_bot, "list_modules", {})
        assert result["modules"] == []

    async def test_module_load_success(self, mock_bot):
        """Module load should succeed for valid module."""

        mock_bot.load_extension = AsyncMock(return_value=None)

        result = await handle_valkey_command(mock_bot, "module_load", {"module": "tagging"})
        assert result["success"] is True

    async def test_module_load_invalid_name(self, mock_bot):
        """Module load should reject invalid module names."""

        result = await handle_valkey_command(mock_bot, "module_load", {"module": ""})
        assert result["success"] is False
        assert "Invalid module name" in result["error"]

        result = await handle_valkey_command(mock_bot, "module_load", {"module": "foo-bar"})
        assert result["success"] is False

        result = await handle_valkey_command(mock_bot, "module_load", {"module": "Foo"})
        assert result["success"] is False

    async def test_module_load_exception(self, mock_bot):
        """Module load should handle load exceptions."""

        mock_bot.load_extension = AsyncMock(side_effect=Exception("Module not found"))

        result = await handle_valkey_command(mock_bot, "module_load", {"module": "invalid"})
        assert result["success"] is False
        assert "Module not found" in result["error"]

    async def test_module_unload_success(self, mock_bot):
        """Module unload should succeed for valid module."""

        mock_bot.unload_extension = AsyncMock(return_value=None)

        result = await handle_valkey_command(mock_bot, "module_unload", {"module": "music"})
        assert result["success"] is True

    async def test_module_unload_invalid_name(self, mock_bot):
        """Module unload should reject invalid module names."""

        result = await handle_valkey_command(mock_bot, "module_unload", {"module": "invalid-module"})
        assert result["success"] is False
        assert "Invalid module name" in result["error"]

    async def test_get_channels_success(self, mock_bot):
        """Get channels should return sorted channel list."""

        mock_channel1 = MagicMock()
        mock_channel1.id = 111
        mock_channel1.name = "general"
        mock_channel1.type.value = 0

        mock_channel2 = MagicMock()
        mock_channel2.id = 222
        mock_channel2.name = "announcements"
        mock_channel2.type.value = 0

        mock_guild = MagicMock()
        mock_guild.channels = [mock_channel1, mock_channel2]
        mock_bot.get_guild = MagicMock(return_value=mock_guild)

        result = await handle_valkey_command(mock_bot, "get_channels", {"guild_id": "123"})
        assert len(result["channels"]) == 2
        assert result["channels"][0]["name"] == "announcements"  # sorted alphabetically
        assert result["channels"][1]["name"] == "general"

    async def test_get_channels_guild_not_found(self, mock_bot):
        """Get channels should handle missing guild."""

        mock_bot.get_guild = MagicMock(return_value=None)

        result = await handle_valkey_command(mock_bot, "get_channels", {"guild_id": "999"})
        assert result["channels"] == []

    async def test_get_roles_success(self, mock_bot):
        """Get roles should return sorted role list excluding @everyone."""

        mock_role1 = MagicMock()
        mock_role1.id = 111
        mock_role1.name = "Admin"
        mock_role1.position = 10
        mock_role1.is_default = MagicMock(return_value=False)

        mock_role2 = MagicMock()
        mock_role2.id = 222
        mock_role2.name = "Member"
        mock_role2.position = 5
        mock_role2.is_default = MagicMock(return_value=False)

        mock_role_default = MagicMock()
        mock_role_default.id = 123
        mock_role_default.name = "@everyone"
        mock_role_default.position = 0
        mock_role_default.is_default = MagicMock(return_value=True)

        mock_guild = MagicMock()
        mock_guild.roles = [mock_role1, mock_role2, mock_role_default]
        mock_bot.get_guild = MagicMock(return_value=mock_guild)

        result = await handle_valkey_command(mock_bot, "get_roles", {"guild_id": "123"})
        assert len(result["roles"]) == 2
        assert result["roles"][0]["name"] == "Admin"  # sorted by position descending
        assert result["roles"][1]["name"] == "Member"

    async def test_get_roles_guild_not_found(self, mock_bot):
        """Get roles should handle missing guild."""

        mock_bot.get_guild = MagicMock(return_value=None)

        result = await handle_valkey_command(mock_bot, "get_roles", {"guild_id": "999"})
        assert result["roles"] == []

    async def test_get_member_names_success(self, mock_bot):
        """Get member names should return mapping of IDs to display names."""

        mock_member1 = MagicMock()
        mock_member1.display_name = "Alice"

        mock_member2 = MagicMock()
        mock_member2.display_name = "Bob"

        mock_guild = MagicMock()
        mock_guild.get_member = lambda uid: mock_member1 if uid == 111 else (mock_member2 if uid == 222 else None)
        mock_bot.get_guild = MagicMock(return_value=mock_guild)

        result = await handle_valkey_command(
            mock_bot, "get_member_names", {"guild_id": "123", "user_ids": ["111", "222", "999"]}
        )
        assert result["111"] == "Alice"
        assert result["222"] == "Bob"
        assert "999" not in result

    async def test_get_member_names_guild_not_found(self, mock_bot):
        """Get member names should handle missing guild."""

        mock_bot.get_guild = MagicMock(return_value=None)

        result = await handle_valkey_command(mock_bot, "get_member_names", {"guild_id": "999", "user_ids": ["111"]})
        assert result == {}

    async def test_post_apply_button_success(self, mock_bot):
        """Post apply button should queue task."""

        mock_task = MagicMock()

        def _fake_ensure_future(coro):
            coro.close()  # prevent unawaited-coroutine warning
            return mock_task

        with patch("utils.valkey.ensure_future", side_effect=_fake_ensure_future):
            result = await handle_valkey_command(mock_bot, "post_apply_button", {"form_id": "42"})
            assert result["queued"] is True

    async def test_post_apply_button_no_form_id(self, mock_bot):
        """Post apply button should require form_id."""

        result = await handle_valkey_command(mock_bot, "post_apply_button", {})
        assert "error" in result
        assert "form_id required" in result["error"]

    async def test_search_realms_success(self, mock_bot):
        """Search realms should return matching realms."""

        mock_wow_cog = MagicMock()
        mock_wow_cog._realm_cache = {
            "eu-silvermoon": {"region": "eu", "name": "Silvermoon", "slug": "silvermoon"},
            "eu-argent-dawn": {"region": "eu", "name": "Argent Dawn", "slug": "argent-dawn"},
            "us-stormrage": {"region": "us", "name": "Stormrage", "slug": "stormrage"},
        }
        mock_wow_cog._ensure_realm_cache = AsyncMock(return_value=None)
        mock_bot.cogs = {"WorldofWarcraft": mock_wow_cog}

        result = await handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "silver"})
        assert len(result["realms"]) == 1
        assert result["realms"][0]["name"] == "Silvermoon"

    async def test_search_realms_no_query(self, mock_bot):
        """Search realms should handle empty query."""

        result = await handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": ""})
        assert result["realms"] == []

        result = await handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "a"})
        assert result["realms"] == []

    async def test_search_realms_module_not_loaded(self, mock_bot):
        """Search realms should handle missing WoW module."""

        mock_bot.cogs = {}

        result = await handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "silver"})
        assert result["realms"] == []
        assert "WoW module not loaded" in result["error"]

    async def test_search_realms_cache_unavailable(self, mock_bot):
        """Search realms should handle cache unavailability."""

        mock_wow_cog = MagicMock()
        mock_wow_cog._ensure_realm_cache = AsyncMock(side_effect=Exception("Timeout"))
        mock_bot.cogs = {"WorldofWarcraft": mock_wow_cog}

        result = await handle_valkey_command(mock_bot, "search_realms", {"region": "eu", "q": "test"})
        assert result["realms"] == []
        assert "Realm cache unavailable" in result["error"]

    async def test_validate_wow_guild_success(self, mock_bot):
        """Validate WoW guild should return valid guild info."""

        mock_wow_cog = MagicMock()
        mock_api = MagicMock()
        mock_api.guild_roster = MagicMock(return_value={"guild": {"name": "Test Guild"}})
        mock_wow_cog._get_retailclient = MagicMock(return_value=mock_api)

        mock_bot.cogs = {"WorldofWarcraft": mock_wow_cog}

        result = await handle_valkey_command(
            mock_bot, "validate_wow_guild", {"region": "eu", "realm_slug": "silvermoon", "guild_name": "test-guild"}
        )
        assert result["valid"] is True
        assert result["display_name"] == "Test Guild"

    async def test_validate_wow_guild_not_found(self, mock_bot):
        """Validate WoW guild should handle 404."""

        mock_wow_cog = MagicMock()
        mock_api = MagicMock()
        mock_api.guild_roster = MagicMock(return_value={"code": 404})
        mock_wow_cog._get_retailclient = MagicMock(return_value=mock_api)

        mock_bot.cogs = {"WorldofWarcraft": mock_wow_cog}

        result = await handle_valkey_command(
            mock_bot, "validate_wow_guild", {"region": "eu", "realm_slug": "silvermoon", "guild_name": "nonexistent"}
        )
        assert result["valid"] is False
        assert result["display_name"] is None

    async def test_validate_wow_guild_rate_limited(self, mock_bot):
        """Validate WoW guild should handle 429 rate limit."""

        mock_wow_cog = MagicMock()
        mock_api = MagicMock()
        mock_api.guild_roster = MagicMock(return_value={"code": 429})
        mock_wow_cog._get_retailclient = MagicMock(return_value=mock_api)

        mock_bot.cogs = {"WorldofWarcraft": mock_wow_cog}
        mock_bot.log = MagicMock()

        result = await handle_valkey_command(
            mock_bot, "validate_wow_guild", {"region": "eu", "realm_slug": "silvermoon", "guild_name": "test"}
        )
        assert result["valid"] is False
        assert "rate limited" in result["error"]

    async def test_validate_wow_guild_empty_params(self, mock_bot):
        """Validate WoW guild should handle missing params."""

        result = await handle_valkey_command(
            mock_bot, "validate_wow_guild", {"region": "eu", "realm_slug": "", "guild_name": "test"}
        )
        assert result["valid"] is False
        assert result["display_name"] is None

    async def test_validate_wow_guild_module_not_loaded(self, mock_bot):
        """Validate WoW guild should handle missing module."""

        mock_bot.cogs = {}

        result = await handle_valkey_command(
            mock_bot, "validate_wow_guild", {"region": "eu", "realm_slug": "silvermoon", "guild_name": "test"}
        )
        assert result["valid"] is False
        assert "WoW module not loaded" in result["error"]

    async def test_validate_wow_guild_exception(self, mock_bot):
        """Validate WoW guild should handle exceptions."""

        mock_wow_cog = MagicMock()
        mock_api = MagicMock()
        mock_api.guild_roster = MagicMock(side_effect=Exception("Network error"))
        mock_wow_cog._get_retailclient = MagicMock(return_value=mock_api)

        mock_bot.cogs = {"WorldofWarcraft": mock_wow_cog}
        mock_bot.log = MagicMock()

        result = await handle_valkey_command(
            mock_bot, "validate_wow_guild", {"region": "eu", "realm_slug": "silvermoon", "guild_name": "test"}
        )
        assert result["valid"] is False
        assert "Network error" in result["error"]

    async def test_unknown_command_returns_error(self, mock_bot):

        result = await handle_valkey_command(mock_bot, "unknown_cmd", {})
        assert "error" in result
        assert "Unknown command" in result["error"]

    async def test_list_guilds_command(self, mock_bot):
        """list_guilds returns info about all bot guilds."""
        mock_guild1 = MagicMock()
        mock_guild1.id = 111111
        mock_guild1.name = "Guild One"
        mock_guild1.icon = MagicMock()
        mock_guild1.icon.key = "abc123"
        mock_guild1.member_count = 42

        mock_guild2 = MagicMock()
        mock_guild2.id = 222222
        mock_guild2.name = "Guild Two"
        mock_guild2.icon = None
        mock_guild2.member_count = 100

        mock_bot.guilds = [mock_guild1, mock_guild2]

        result = await handle_valkey_command(mock_bot, "list_guilds", {})
        assert len(result["guilds"]) == 2
        assert result["guilds"][0]["id"] == "111111"
        assert result["guilds"][0]["name"] == "Guild One"
        assert result["guilds"][0]["icon"] == "abc123"
        assert result["guilds"][0]["member_count"] == 42
        assert result["guilds"][1]["icon"] is None

    async def test_list_guilds_empty(self, mock_bot):
        """list_guilds returns empty list when bot is in no guilds."""
        mock_bot.guilds = []
        result = await handle_valkey_command(mock_bot, "list_guilds", {})
        assert result["guilds"] == []
