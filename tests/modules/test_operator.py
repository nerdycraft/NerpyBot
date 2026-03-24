# -*- coding: utf-8 -*-
"""Tests for Operator cog: botpermissions, !disable/!enable/!disabled/!help/!errors commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import HTTPException, Object
from discord.app_commands import MissingApplicationID
from models.admin import PermissionSubscriber
from modules.operator import Operator, _format_remaining
from utils.errors import NerpyInfraException
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    mock_bot.ops = [123456789]
    mock_bot.error_throttle = MagicMock()
    mock_bot.disabled_modules = set()
    mock_bot.extensions = {
        "modules.server_admin": MagicMock(),
        "modules.operator": MagicMock(),
        "modules.wow": MagicMock(),
        "modules.league": MagicMock(),
        "modules.music": MagicMock(),
        "modules.voicecontrol": MagicMock(),
    }
    return Operator(mock_bot)


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    mock_interaction.user.id = 123456789
    return mock_interaction


@pytest.fixture
def operator_ctx(mock_bot):
    ctx = MagicMock()
    ctx.bot = mock_bot
    ctx.author = MagicMock()
    ctx.author.id = 123456789
    ctx.user = ctx.author
    ctx.client = mock_bot
    ctx.send = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# /botpermissions subscribe
# ---------------------------------------------------------------------------


class TestBotpermissionsSubscribe:
    async def test_subscribe_success(self, cog, interaction, db_session):
        await Operator.botpermissions._children["subscribe"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Subscribed" in msg

    async def test_subscribe_already(self, cog, interaction, db_session):
        db_session.add(PermissionSubscriber(GuildId=987654321, UserId=123456789))
        db_session.commit()

        await Operator.botpermissions._children["subscribe"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "already subscribed" in msg


# ---------------------------------------------------------------------------
# /botpermissions unsubscribe
# ---------------------------------------------------------------------------


class TestBotpermissionsUnsubscribe:
    async def test_unsubscribe_not_subscribed(self, cog, interaction):
        await Operator.botpermissions._children["unsubscribe"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "not subscribed" in msg

    async def test_unsubscribe_success(self, cog, interaction, db_session):
        db_session.add(PermissionSubscriber(GuildId=987654321, UserId=123456789))
        db_session.commit()

        await Operator.botpermissions._children["unsubscribe"].callback(cog, interaction)

        msg = interaction.response.send_message.call_args[0][0]
        assert "Unsubscribed" in msg


# ---------------------------------------------------------------------------
# !disable
# ---------------------------------------------------------------------------


class TestDisableCommand:
    @pytest.mark.asyncio
    async def test_disables_loaded_module(self, cog, operator_ctx):
        await cog._disable.callback(cog, operator_ctx, module="wow")
        assert "wow" in cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "disabled" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_unknown_module(self, cog, operator_ctx):
        await cog._disable.callback(cog, operator_ctx, module="doesnotexist")
        assert "doesnotexist" not in cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "not loaded" in msg.lower() or "Unknown" in msg

    @pytest.mark.asyncio
    async def test_rejects_protected_module(self, cog, operator_ctx):
        await cog._disable.callback(cog, operator_ctx, module="server_admin")
        assert "server_admin" not in cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "cannot" in msg.lower() or "protected" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_already_disabled(self, cog, operator_ctx):
        cog.bot.disabled_modules.add("wow")
        await cog._disable.callback(cog, operator_ctx, module="wow")
        msg = operator_ctx.send.call_args[0][0]
        assert "already" in msg.lower()


# ---------------------------------------------------------------------------
# !enable
# ---------------------------------------------------------------------------


class TestEnableCommand:
    @pytest.mark.asyncio
    async def test_enables_disabled_module(self, cog, operator_ctx):
        cog.bot.disabled_modules.add("wow")
        await cog._enable.callback(cog, operator_ctx, module="wow")
        assert "wow" not in cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "enabled" in msg.lower() or "re-enabled" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_not_disabled(self, cog, operator_ctx):
        await cog._enable.callback(cog, operator_ctx, module="wow")
        msg = operator_ctx.send.call_args[0][0]
        assert "not disabled" in msg.lower()

    @pytest.mark.asyncio
    async def test_enable_all_clears_disabled_set(self, cog, operator_ctx):
        cog.bot.disabled_modules = {"wow", "league"}
        await cog._enable.callback(cog, operator_ctx, module=None)
        assert len(cog.bot.disabled_modules) == 0
        msg = operator_ctx.send.call_args[0][0]
        assert "all modules" in msg.lower()
        assert "wow" in msg
        assert "league" in msg

    @pytest.mark.asyncio
    async def test_enable_all_when_none_disabled(self, cog, operator_ctx):
        await cog._enable.callback(cog, operator_ctx, module=None)
        msg = operator_ctx.send.call_args[0][0]
        assert "no modules" in msg.lower()


# ---------------------------------------------------------------------------
# !disabled
# ---------------------------------------------------------------------------


class TestDisabledCommand:
    @pytest.mark.asyncio
    async def test_lists_disabled_modules(self, cog, operator_ctx):
        cog.bot.disabled_modules = {"wow", "league"}
        await cog._disabled.callback(cog, operator_ctx)
        msg = operator_ctx.send.call_args[0][0]
        assert "wow" in msg
        assert "league" in msg

    @pytest.mark.asyncio
    async def test_shows_none_when_all_enabled(self, cog, operator_ctx):
        await cog._disabled.callback(cog, operator_ctx)
        msg = operator_ctx.send.call_args[0][0]
        assert "no modules" in msg.lower() or "all modules" in msg.lower()


# ---------------------------------------------------------------------------
# !help
# ---------------------------------------------------------------------------


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_lists_operator_commands(self, cog, operator_ctx):
        cmd_disable = MagicMock()
        cmd_disable.qualified_name = "disable"
        cmd_disable.help = "Disable a module at runtime. [operator]"
        cmd_disable.short_doc = "Disable a module at runtime. [operator]"

        cmd_ping = MagicMock()
        cmd_ping.qualified_name = "ping"
        cmd_ping.help = "Pong."
        cmd_ping.short_doc = "Pong."

        cog.bot.commands = [cmd_disable, cmd_ping]

        await cog._help.callback(cog, operator_ctx, name=None)
        msg = operator_ctx.send.call_args[0][0]
        assert "!disable" in msg
        assert "ping" not in msg  # ping has no [operator] tag
        assert "!help <command>" in msg

    @pytest.mark.asyncio
    async def test_shows_header(self, cog, operator_ctx):
        cog.bot.commands = []
        await cog._help.callback(cog, operator_ctx, name=None)
        msg = operator_ctx.send.call_args[0][0]
        assert "Operator Commands" in msg

    @pytest.mark.asyncio
    async def test_detail_view_shows_full_docstring(self, cog, operator_ctx):
        cmd_errors = MagicMock()
        cmd_errors.qualified_name = "errors"
        cmd_errors.help = "Manage error notifications. [operator]\n\nSubcommands:\n  status — Show status"

        cog.bot.get_command = MagicMock(return_value=cmd_errors)

        await cog._help.callback(cog, operator_ctx, name="errors")
        msg = operator_ctx.send.call_args[0][0]
        assert "!errors" in msg
        assert "Subcommands" in msg
        assert "status" in msg

    @pytest.mark.asyncio
    async def test_detail_view_unknown_command(self, cog, operator_ctx):
        cog.bot.get_command = MagicMock(return_value=None)

        await cog._help.callback(cog, operator_ctx, name="nope")
        msg = operator_ctx.send.call_args[0][0]
        assert "Unknown" in msg

    @pytest.mark.asyncio
    async def test_detail_view_rejects_non_operator_command(self, cog, operator_ctx):
        cmd_ping = MagicMock()
        cmd_ping.help = "Pong."

        cog.bot.get_command = MagicMock(return_value=cmd_ping)

        await cog._help.callback(cog, operator_ctx, name="ping")
        msg = operator_ctx.send.call_args[0][0]
        assert "Unknown" in msg


# ---------------------------------------------------------------------------
# !errors
# ---------------------------------------------------------------------------


class TestErrorsDefaultAction:
    @pytest.mark.asyncio
    async def test_no_action_defaults_to_status(self, cog, operator_ctx):
        cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": False,
            "suppressed_remaining": None,
            "throttle_window": 900,
            "buckets": {},
        }
        await cog._errors.callback(cog, operator_ctx, action="status")
        operator_ctx.send.assert_awaited_once()
        msg = operator_ctx.send.call_args[0][0]
        assert "\U0001f514" in msg


class TestErrorsSuppress:
    @pytest.mark.asyncio
    async def test_suppress_valid_duration(self, cog, operator_ctx):
        await cog._errors.callback(cog, operator_ctx, action="suppress", arg="30m")
        cog.bot.error_throttle.suppress.assert_called_once_with(1800)

    @pytest.mark.asyncio
    async def test_suppress_missing_duration(self, cog, operator_ctx):
        await cog._errors.callback(cog, operator_ctx, action="suppress", arg=None)
        cog.bot.error_throttle.suppress.assert_not_called()
        msg = operator_ctx.send.call_args[0][0]
        assert "Usage" in msg

    @pytest.mark.asyncio
    async def test_suppress_invalid_duration(self, cog, operator_ctx):
        await cog._errors.callback(cog, operator_ctx, action="suppress", arg="banana")
        cog.bot.error_throttle.suppress.assert_not_called()
        msg = operator_ctx.send.call_args[0][0]
        assert "Invalid" in msg


class TestErrorsResume:
    @pytest.mark.asyncio
    async def test_resume_when_suppressed(self, cog, operator_ctx):
        cog.bot.error_throttle.is_suppressed = True
        await cog._errors.callback(cog, operator_ctx, action="resume")
        cog.bot.error_throttle.resume.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_when_not_suppressed(self, cog, operator_ctx):
        cog.bot.error_throttle.is_suppressed = False
        await cog._errors.callback(cog, operator_ctx, action="resume")
        cog.bot.error_throttle.resume.assert_not_called()
        msg = operator_ctx.send.call_args[0][0]
        assert "already active" in msg


class TestErrorsStatus:
    @pytest.mark.asyncio
    async def test_status_active_with_buckets(self, cog, operator_ctx):
        cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": False,
            "suppressed_remaining": None,
            "throttle_window": 900,
            "buckets": {
                "ValueError:Reminder loop": {"last_notified_ago": 300.0, "suppressed_count": 2},
            },
        }
        await cog._errors.callback(cog, operator_ctx, action="status")
        msg = operator_ctx.send.call_args[0][0]
        assert "\U0001f514" in msg
        assert "ValueError:Reminder loop" in msg
        assert "2 suppressed" in msg

    @pytest.mark.asyncio
    async def test_status_suppressed(self, cog, operator_ctx):
        cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": True,
            "suppressed_remaining": 5000.0,
            "throttle_window": 900,
            "buckets": {},
        }
        await cog._errors.callback(cog, operator_ctx, action="status")
        msg = operator_ctx.send.call_args[0][0]
        assert "\U0001f507" in msg

    @pytest.mark.asyncio
    async def test_status_no_buckets(self, cog, operator_ctx):
        cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": False,
            "suppressed_remaining": None,
            "throttle_window": 900,
            "buckets": {},
        }
        await cog._errors.callback(cog, operator_ctx, action="status")
        msg = operator_ctx.send.call_args[0][0]
        assert "No errors tracked" in msg


class TestErrorsUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self, cog, operator_ctx):
        await cog._errors.callback(cog, operator_ctx, action="foobar")
        msg = operator_ctx.send.call_args[0][0]
        assert "Unknown action" in msg


# ---------------------------------------------------------------------------
# !sync (multi-guild path)
# ---------------------------------------------------------------------------


class TestSyncGuilds:
    def _make_guilds(self, *ids):
        return [Object(id=i) for i in ids]

    @pytest.mark.asyncio
    async def test_all_guilds_succeed(self, cog, operator_ctx):
        cog.bot.tree.sync = AsyncMock(return_value=[])
        guilds = self._make_guilds(1, 2, 3)

        await cog.sync.callback(cog, operator_ctx, guilds=guilds, spec=None)

        msg = operator_ctx.send.call_args[0][0]
        assert "3/3" in msg

    @pytest.mark.asyncio
    async def test_partial_failure_http_exception(self, cog, operator_ctx):
        http_err = HTTPException(MagicMock(status=429), "rate limited")

        async def side_effect(guild):
            if guild.id == 2:
                raise http_err
            return []

        cog.bot.tree.sync = side_effect
        guilds = self._make_guilds(1, 2, 3)

        await cog.sync.callback(cog, operator_ctx, guilds=guilds, spec=None)

        msg = operator_ctx.send.call_args[0][0]
        assert "2/3" in msg

    @pytest.mark.asyncio
    async def test_hard_error_raises_infra_exception_after_all_complete(self, cog, operator_ctx):
        sync_calls = []

        async def side_effect(guild):
            sync_calls.append(guild)
            if guild.id == 2:
                raise MissingApplicationID("boom")
            return []

        cog.bot.tree.sync = side_effect
        guilds = self._make_guilds(1, 2, 3)

        with pytest.raises(NerpyInfraException):
            await cog.sync.callback(cog, operator_ctx, guilds=guilds, spec=None)

        # All three guilds must have been attempted before the exception propagated
        assert len(sync_calls) == 3

    @pytest.mark.asyncio
    async def test_unexpected_exception_raises_infra_exception(self, cog, operator_ctx):
        async def side_effect(guild):
            if guild.id == 2:
                raise RuntimeError("unexpected")
            return []

        cog.bot.tree.sync = side_effect
        guilds = self._make_guilds(1, 2, 3)

        with pytest.raises(NerpyInfraException):
            await cog.sync.callback(cog, operator_ctx, guilds=guilds, spec=None)

    @pytest.mark.asyncio
    async def test_single_guild_succeeds(self, cog, operator_ctx):
        cog.bot.tree.sync = AsyncMock(return_value=[])
        guilds = self._make_guilds(42)

        await cog.sync.callback(cog, operator_ctx, guilds=guilds, spec=None)

        msg = operator_ctx.send.call_args[0][0]
        assert "1/1" in msg


# ---------------------------------------------------------------------------
# _format_remaining helper
# ---------------------------------------------------------------------------


class TestFormatRemaining:
    def test_seconds(self):
        assert _format_remaining(45) == "45s"

    def test_minutes(self):
        assert _format_remaining(300) == "5m"

    def test_hours_and_minutes(self):
        assert _format_remaining(4980) == "1h 23m"

    def test_days_and_hours(self):
        assert _format_remaining(90000) == "1d 1h"

    def test_exact_hour(self):
        assert _format_remaining(3600) == "1h"
