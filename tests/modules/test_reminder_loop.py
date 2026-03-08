# -*- coding: utf-8 -*-
"""Tests for Reminder background loop body — firing, rescheduling, and pruning."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.reminder import ReminderMessage
from modules.reminder import Reminder
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    """Load locale YAML files before each test."""
    load_strings()


@pytest.fixture
def reminder_cog(mock_bot):
    """Instantiate Reminder with the background loop fully stopped."""
    with patch.object(Reminder, "_reminder_loop"):
        cog = Reminder.__new__(Reminder)
        cog.bot = mock_bot
        cog._reminder_loop = MagicMock()
        cog._reminder_loop.start = MagicMock()
        cog._reminder_loop.cancel = MagicMock()
        cog._reminder_loop.restart = MagicMock()
        cog._reminder_loop.change_interval = MagicMock()
    return cog


def _make_reminder(db_session, **overrides):
    """Insert a ReminderMessage with sensible defaults (already due)."""
    now = datetime.now(UTC)
    defaults = dict(
        GuildId=123,
        ChannelId=456,
        ChannelName="general",
        CreateDate=now,
        Author="Tester",
        ScheduleType="interval",
        IntervalSeconds=3600,
        NextFire=now - timedelta(minutes=5),
        Message="Test reminder",
        Count=0,
        Enabled=True,
    )
    defaults.update(overrides)
    r = ReminderMessage(**defaults)
    db_session.add(r)
    db_session.commit()
    return r


class TestReminderLoop:
    """Tests for the _reminder_loop body via direct _fire_reminder calls."""

    @pytest.mark.asyncio
    async def test_loop_fires_due_interval_reminder(self, reminder_cog, db_session):
        """A due interval reminder should be sent and NextFire updated to a future time."""
        r = _make_reminder(db_session, ScheduleType="interval", IntervalSeconds=3600)
        original_next_fire = r.NextFire

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.id = 123
        mock_guild.get_channel = MagicMock(return_value=mock_channel)

        reminder_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        with reminder_cog.bot.session_scope() as session:
            await reminder_cog._fire_reminder(r, session)

        mock_channel.send.assert_awaited_once_with("Test reminder")

        # NextFire must have been rescheduled into the future
        assert r.NextFire != original_next_fire
        assert r.NextFire.replace(tzinfo=UTC) > datetime.now(UTC)

    @pytest.mark.asyncio
    async def test_loop_deletes_fired_once_reminder(self, reminder_cog, db_session):
        """A one-shot (once) reminder should be deleted from the DB after firing."""
        r = _make_reminder(db_session, ScheduleType="once", IntervalSeconds=None)
        rid = r.Id

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()

        mock_guild = MagicMock()
        mock_guild.id = 123
        mock_guild.get_channel = MagicMock(return_value=mock_channel)

        reminder_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        with reminder_cog.bot.session_scope() as session:
            await reminder_cog._fire_reminder(r, session)

        mock_channel.send.assert_awaited_once_with("Test reminder")

        # Row must be gone — session auto-flushes before querying
        assert ReminderMessage.get_by_id(rid, 123, db_session) is None

    @pytest.mark.asyncio
    async def test_loop_deletes_reminder_when_channel_gone(self, reminder_cog, db_session):
        """When the channel is missing, the reminder should be deleted from the DB."""
        r = _make_reminder(db_session)
        rid = r.Id

        mock_guild = MagicMock()
        mock_guild.id = 123
        mock_guild.get_channel = MagicMock(return_value=None)
        mock_guild.get_thread = MagicMock(return_value=None)

        reminder_cog.bot.get_guild = MagicMock(return_value=mock_guild)

        with reminder_cog.bot.session_scope() as session:
            await reminder_cog._fire_reminder(r, session)

        # No message was sent (channel was None); the row should be deleted
        assert ReminderMessage.get_by_id(rid, 123, db_session) is None
