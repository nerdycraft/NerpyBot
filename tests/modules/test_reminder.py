# tests/modules/test_reminder.py
# -*- coding: utf-8 -*-
"""Tests for modules/reminder.py — Reminder cog commands."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from models.reminder import ReminderMessage
from modules.reminder import Reminder


@pytest.fixture
def reminder_cog(mock_bot):
    """Create a Reminder cog with the loop stopped (we test commands, not the loop)."""
    with patch.object(Reminder, "_reminder_loop"):
        cog = Reminder.__new__(Reminder)
        cog.bot = mock_bot
        cog._reminder_loop = MagicMock()
        cog._reminder_loop.start = MagicMock()
        cog._reminder_loop.cancel = MagicMock()
        cog._reminder_loop.restart = MagicMock()
        cog._reminder_loop.change_interval = MagicMock()
    return cog


class TestReminderCreate:
    """Tests for /reminder create command logic."""

    @pytest.mark.asyncio
    async def test_create_oneshot(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        mock_interaction.channel.id = 456
        mock_interaction.channel.name = "general"
        mock_interaction.channel.permissions_for = MagicMock(
            return_value=MagicMock(view_channel=True, send_messages=True)
        )

        await reminder_cog._reminder_create.callback(
            reminder_cog, mock_interaction, delay="2h", message="Test", channel=None, repeat=False
        )

        mock_interaction.response.send_message.assert_called_once()
        call_kwargs = mock_interaction.response.send_message.call_args
        assert "created" in str(call_kwargs).lower()

        # Verify DB state
        reminders = ReminderMessage.get_all_by_guild(123, db_session)
        assert len(reminders) == 1
        assert reminders[0].ScheduleType == "once"
        assert reminders[0].IntervalSeconds is None
        assert reminders[0].Message == "Test"

    @pytest.mark.asyncio
    async def test_create_repeating(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        mock_interaction.channel.id = 456
        mock_interaction.channel.name = "general"
        mock_interaction.channel.permissions_for = MagicMock(
            return_value=MagicMock(view_channel=True, send_messages=True)
        )

        await reminder_cog._reminder_create.callback(
            reminder_cog, mock_interaction, delay="1d", message="Daily", channel=None, repeat=True
        )

        reminders = ReminderMessage.get_all_by_guild(123, db_session)
        assert len(reminders) == 1
        assert reminders[0].ScheduleType == "interval"
        assert reminders[0].IntervalSeconds == 86400

    @pytest.mark.asyncio
    async def test_create_invalid_duration(self, reminder_cog, mock_interaction, db_session):
        await reminder_cog._reminder_create.callback(
            reminder_cog, mock_interaction, delay="nope", message="Test", channel=None, repeat=False
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "Could not parse" in call_args
        assert ReminderMessage.get_all_by_guild(123, db_session) == []

    @pytest.mark.asyncio
    async def test_create_too_short_duration(self, reminder_cog, mock_interaction, db_session):
        await reminder_cog._reminder_create.callback(
            reminder_cog, mock_interaction, delay="30s", message="Test", channel=None, repeat=False
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "60 seconds" in call_args


class TestReminderSchedule:
    """Tests for /reminder schedule command logic."""

    @pytest.mark.asyncio
    async def test_schedule_daily(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        mock_interaction.channel.id = 456
        mock_interaction.channel.name = "general"
        mock_interaction.channel.permissions_for = MagicMock(
            return_value=MagicMock(view_channel=True, send_messages=True)
        )

        stype = MagicMock()
        stype.value = "daily"

        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            mock_interaction,
            schedule_type=stype,
            time_of_day="09:00",
            message="Good morning",
            channel=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        reminders = ReminderMessage.get_all_by_guild(123, db_session)
        assert len(reminders) == 1
        assert reminders[0].ScheduleType == "daily"
        assert reminders[0].ScheduleTime.hour == 9
        assert reminders[0].ScheduleTime.minute == 0

    @pytest.mark.asyncio
    async def test_schedule_weekly_requires_day(self, reminder_cog, mock_interaction, db_session):
        stype = MagicMock()
        stype.value = "weekly"

        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            mock_interaction,
            schedule_type=stype,
            time_of_day="09:00",
            message="Sync",
            channel=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "day_of_week" in call_args

    @pytest.mark.asyncio
    async def test_schedule_monthly_validates_range(self, reminder_cog, mock_interaction, db_session):
        stype = MagicMock()
        stype.value = "monthly"

        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            mock_interaction,
            schedule_type=stype,
            time_of_day="12:00",
            message="Rent",
            channel=None,
            day_of_week=None,
            day_of_month=31,
            timezone=None,
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "1 and 28" in call_args

    @pytest.mark.asyncio
    async def test_schedule_invalid_time_format(self, reminder_cog, mock_interaction, db_session):
        stype = MagicMock()
        stype.value = "daily"

        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            mock_interaction,
            schedule_type=stype,
            time_of_day="invalid",
            message="Test",
            channel=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "HH:MM" in call_args


class TestReminderPauseResume:
    """Tests for /reminder pause and resume."""

    @pytest.mark.asyncio
    async def test_pause_sets_enabled_false(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=now + timedelta(hours=1),
            Message="Test",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()

        await reminder_cog._reminder_pause.callback(reminder_cog, mock_interaction, reminder_id=r.Id)

        # No refresh needed — r and the cog's msg are the same identity-mapped object
        assert r.Enabled is False

    @pytest.mark.asyncio
    async def test_resume_sets_enabled_true(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=now + timedelta(hours=1),
            Message="Test",
            Count=0,
            Enabled=False,
        )
        db_session.add(r)
        db_session.commit()

        await reminder_cog._reminder_resume.callback(reminder_cog, mock_interaction, reminder_id=r.Id)

        assert r.Enabled is True

    @pytest.mark.asyncio
    async def test_resume_recalculates_past_next_fire(self, reminder_cog, mock_interaction, db_session):
        """Resume should recalculate NextFire if it's in the past."""
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        past = now - timedelta(days=2)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=past,
            Message="Test",
            Count=0,
            Enabled=False,
        )
        db_session.add(r)
        db_session.commit()

        await reminder_cog._reminder_resume.callback(reminder_cog, mock_interaction, reminder_id=r.Id)

        assert r.Enabled is True
        # NextFire should be recalculated to the future
        assert r.NextFire.replace(tzinfo=UTC) > now

    @pytest.mark.asyncio
    async def test_pause_nonexistent_returns_not_found(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        await reminder_cog._reminder_pause.callback(reminder_cog, mock_interaction, reminder_id=99999)
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()


class TestReminderDelete:
    """Tests for /reminder delete."""

    @pytest.mark.asyncio
    async def test_delete_removes_from_db(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="once",
            NextFire=now + timedelta(hours=1),
            Message="Delete me",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()
        rid = r.Id

        await reminder_cog._reminder_delete.callback(reminder_cog, mock_interaction, reminder_id=rid)

        assert ReminderMessage.get_by_id(rid, 123, db_session) is None
