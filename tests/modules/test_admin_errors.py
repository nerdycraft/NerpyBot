# -*- coding: utf-8 -*-
"""Tests for admin !errors operator commands and duration helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.admin import Admin, _format_remaining, _parse_duration


@pytest.fixture
def admin_cog(mock_bot):
    mock_bot.ops = [123456789]
    mock_bot.error_throttle = MagicMock()
    return Admin(mock_bot)


@pytest.fixture
def operator_ctx(mock_bot):
    ctx = MagicMock()
    ctx.bot = mock_bot
    ctx.author = MagicMock()
    ctx.author.id = 123456789  # in ops list
    # require_operator() falls through to the Interaction branch for plain MagicMock
    # (not isinstance Context), so provide .user and .client as well.
    ctx.user = ctx.author
    ctx.client = mock_bot
    ctx.send = AsyncMock()
    return ctx


class TestErrorsDefaultAction:
    @pytest.mark.asyncio
    async def test_no_action_defaults_to_status(self, admin_cog, operator_ctx):
        admin_cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": False,
            "suppressed_remaining": None,
            "throttle_window": 900,
            "buckets": {},
        }
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="status")
        operator_ctx.send.assert_awaited_once()
        msg = operator_ctx.send.call_args[0][0]
        assert "\U0001f514" in msg


class TestErrorsSuppress:
    @pytest.mark.asyncio
    async def test_suppress_valid_duration(self, admin_cog, operator_ctx):
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="suppress", arg="30m")
        admin_cog.bot.error_throttle.suppress.assert_called_once_with(1800)

    @pytest.mark.asyncio
    async def test_suppress_missing_duration(self, admin_cog, operator_ctx):
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="suppress", arg=None)
        admin_cog.bot.error_throttle.suppress.assert_not_called()
        msg = operator_ctx.send.call_args[0][0]
        assert "Usage" in msg

    @pytest.mark.asyncio
    async def test_suppress_invalid_duration(self, admin_cog, operator_ctx):
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="suppress", arg="banana")
        admin_cog.bot.error_throttle.suppress.assert_not_called()
        msg = operator_ctx.send.call_args[0][0]
        assert "Invalid" in msg


class TestErrorsResume:
    @pytest.mark.asyncio
    async def test_resume_when_suppressed(self, admin_cog, operator_ctx):
        admin_cog.bot.error_throttle.is_suppressed = True
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="resume")
        admin_cog.bot.error_throttle.resume.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_when_not_suppressed(self, admin_cog, operator_ctx):
        admin_cog.bot.error_throttle.is_suppressed = False
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="resume")
        admin_cog.bot.error_throttle.resume.assert_not_called()
        msg = operator_ctx.send.call_args[0][0]
        assert "already active" in msg


class TestErrorsStatus:
    @pytest.mark.asyncio
    async def test_status_active_with_buckets(self, admin_cog, operator_ctx):
        admin_cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": False,
            "suppressed_remaining": None,
            "throttle_window": 900,
            "buckets": {
                "ValueError:Reminder loop": {"last_notified_ago": 300.0, "suppressed_count": 2},
            },
        }
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="status")
        msg = operator_ctx.send.call_args[0][0]
        assert "\U0001f514" in msg
        assert "ValueError:Reminder loop" in msg
        assert "2 suppressed" in msg

    @pytest.mark.asyncio
    async def test_status_suppressed(self, admin_cog, operator_ctx):
        admin_cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": True,
            "suppressed_remaining": 5000.0,
            "throttle_window": 900,
            "buckets": {},
        }
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="status")
        msg = operator_ctx.send.call_args[0][0]
        assert "\U0001f507" in msg

    @pytest.mark.asyncio
    async def test_status_no_buckets(self, admin_cog, operator_ctx):
        admin_cog.bot.error_throttle.get_status.return_value = {
            "is_suppressed": False,
            "suppressed_remaining": None,
            "throttle_window": 900,
            "buckets": {},
        }
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="status")
        msg = operator_ctx.send.call_args[0][0]
        assert "No errors tracked" in msg


class TestErrorsUnknownAction:
    @pytest.mark.asyncio
    async def test_unknown_action(self, admin_cog, operator_ctx):
        await admin_cog._errors.callback(admin_cog, operator_ctx, action="foobar")
        msg = operator_ctx.send.call_args[0][0]
        assert "Unknown action" in msg


class TestParseDuration:
    def test_minutes(self):
        assert _parse_duration("30m") == 1800

    def test_hours(self):
        assert _parse_duration("2h") == 7200

    def test_days(self):
        assert _parse_duration("1d") == 86400

    def test_with_spaces(self):
        assert _parse_duration(" 15 m ") == 900

    def test_invalid_returns_none(self):
        assert _parse_duration("banana") is None

    def test_empty_returns_none(self):
        assert _parse_duration("") is None


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
