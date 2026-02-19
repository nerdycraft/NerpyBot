# -*- coding: utf-8 -*-
"""Tests for admin !disable / !enable / !disabled / !help operator commands."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.admin import Admin


@pytest.fixture
def admin_cog(mock_bot):
    mock_bot.ops = [123456789]
    mock_bot.error_throttle = MagicMock()
    mock_bot.disabled_modules = set()
    mock_bot.extensions = {
        "modules.admin": MagicMock(),
        "modules.wow": MagicMock(),
        "modules.league": MagicMock(),
        "modules.music": MagicMock(),
        "modules.voicecontrol": MagicMock(),
    }
    return Admin(mock_bot)


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


class TestDisableCommand:
    @pytest.mark.asyncio
    async def test_disables_loaded_module(self, admin_cog, operator_ctx):
        await admin_cog._disable.callback(admin_cog, operator_ctx, module="wow")
        assert "wow" in admin_cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "disabled" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_unknown_module(self, admin_cog, operator_ctx):
        await admin_cog._disable.callback(admin_cog, operator_ctx, module="doesnotexist")
        assert "doesnotexist" not in admin_cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "not loaded" in msg.lower() or "Unknown" in msg

    @pytest.mark.asyncio
    async def test_rejects_protected_module(self, admin_cog, operator_ctx):
        await admin_cog._disable.callback(admin_cog, operator_ctx, module="admin")
        assert "admin" not in admin_cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "cannot" in msg.lower() or "protected" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_already_disabled(self, admin_cog, operator_ctx):
        admin_cog.bot.disabled_modules.add("wow")
        await admin_cog._disable.callback(admin_cog, operator_ctx, module="wow")
        msg = operator_ctx.send.call_args[0][0]
        assert "already" in msg.lower()


class TestEnableCommand:
    @pytest.mark.asyncio
    async def test_enables_disabled_module(self, admin_cog, operator_ctx):
        admin_cog.bot.disabled_modules.add("wow")
        await admin_cog._enable.callback(admin_cog, operator_ctx, module="wow")
        assert "wow" not in admin_cog.bot.disabled_modules
        msg = operator_ctx.send.call_args[0][0]
        assert "enabled" in msg.lower() or "re-enabled" in msg.lower()

    @pytest.mark.asyncio
    async def test_rejects_not_disabled(self, admin_cog, operator_ctx):
        await admin_cog._enable.callback(admin_cog, operator_ctx, module="wow")
        msg = operator_ctx.send.call_args[0][0]
        assert "not disabled" in msg.lower()

    @pytest.mark.asyncio
    async def test_enable_all_clears_disabled_set(self, admin_cog, operator_ctx):
        admin_cog.bot.disabled_modules = {"wow", "league"}
        await admin_cog._enable.callback(admin_cog, operator_ctx, module=None)
        assert len(admin_cog.bot.disabled_modules) == 0
        msg = operator_ctx.send.call_args[0][0]
        assert "all modules" in msg.lower()
        assert "wow" in msg
        assert "league" in msg

    @pytest.mark.asyncio
    async def test_enable_all_when_none_disabled(self, admin_cog, operator_ctx):
        await admin_cog._enable.callback(admin_cog, operator_ctx, module=None)
        msg = operator_ctx.send.call_args[0][0]
        assert "no modules" in msg.lower()


class TestDisabledCommand:
    @pytest.mark.asyncio
    async def test_lists_disabled_modules(self, admin_cog, operator_ctx):
        admin_cog.bot.disabled_modules = {"wow", "league"}
        await admin_cog._disabled.callback(admin_cog, operator_ctx)
        msg = operator_ctx.send.call_args[0][0]
        assert "wow" in msg
        assert "league" in msg

    @pytest.mark.asyncio
    async def test_shows_none_when_all_enabled(self, admin_cog, operator_ctx):
        await admin_cog._disabled.callback(admin_cog, operator_ctx)
        msg = operator_ctx.send.call_args[0][0]
        assert "no modules" in msg.lower() or "all modules" in msg.lower()


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_lists_operator_commands(self, admin_cog, operator_ctx):
        cmd_disable = MagicMock()
        cmd_disable.qualified_name = "disable"
        cmd_disable.help = "Disable a module at runtime. [operator]"
        cmd_disable.short_doc = "Disable a module at runtime. [operator]"

        cmd_ping = MagicMock()
        cmd_ping.qualified_name = "ping"
        cmd_ping.help = "Pong."
        cmd_ping.short_doc = "Pong."

        admin_cog.bot.commands = [cmd_disable, cmd_ping]

        await admin_cog._help.callback(admin_cog, operator_ctx, name=None)
        msg = operator_ctx.send.call_args[0][0]
        assert "!disable" in msg
        assert "ping" not in msg  # ping has no [operator] tag
        assert "!help <command>" in msg

    @pytest.mark.asyncio
    async def test_shows_header(self, admin_cog, operator_ctx):
        admin_cog.bot.commands = []
        await admin_cog._help.callback(admin_cog, operator_ctx, name=None)
        msg = operator_ctx.send.call_args[0][0]
        assert "Operator Commands" in msg

    @pytest.mark.asyncio
    async def test_detail_view_shows_full_docstring(self, admin_cog, operator_ctx):
        cmd_errors = MagicMock()
        cmd_errors.qualified_name = "errors"
        cmd_errors.help = "Manage error notifications. [operator]\n\nSubcommands:\n  status — Show status"

        admin_cog.bot.get_command = MagicMock(return_value=cmd_errors)

        await admin_cog._help.callback(admin_cog, operator_ctx, name="errors")
        msg = operator_ctx.send.call_args[0][0]
        assert "!errors" in msg
        assert "Subcommands" in msg
        assert "status" in msg

    @pytest.mark.asyncio
    async def test_detail_view_unknown_command(self, admin_cog, operator_ctx):
        admin_cog.bot.get_command = MagicMock(return_value=None)

        await admin_cog._help.callback(admin_cog, operator_ctx, name="nope")
        msg = operator_ctx.send.call_args[0][0]
        assert "Unknown" in msg

    @pytest.mark.asyncio
    async def test_detail_view_rejects_non_operator_command(self, admin_cog, operator_ctx):
        cmd_ping = MagicMock()
        cmd_ping.help = "Pong."

        admin_cog.bot.get_command = MagicMock(return_value=cmd_ping)

        await admin_cog._help.callback(admin_cog, operator_ctx, name="ping")
        msg = operator_ctx.send.call_args[0][0]
        assert "Unknown" in msg
