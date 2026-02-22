# tests/modules/test_reminder.py
# -*- coding: utf-8 -*-
"""Tests for modules/reminder.py — Reminder cog commands."""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.admin import GuildLanguageConfig
from models.reminder import ReminderMessage
from modules.reminder import Reminder, _format_relative
from utils.strings import load_strings


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


class TestFormatRelative:
    """Tests for _format_relative — calendar-day-aware relative time."""

    def test_short_duration_uses_humanize(self):
        """Under 12 hours should use humanize for precision."""
        next_fire = datetime.now(UTC) + timedelta(hours=2)
        result = _format_relative(next_fire)
        assert "hour" in result

    def test_same_timezone_calendar_days(self):
        """Two calendar days in the same timezone should say '2 days from now'."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Berlin")
        # Build a fire time 2 calendar days from now at 09:00 local
        local_now = datetime.now(tz)
        fire_date = (local_now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
        fire_utc = fire_date.astimezone(UTC)
        result = _format_relative(fire_utc, tz)
        assert result == "2 days from now"

    def test_different_timezones_same_calendar_day_count(self):
        """Both Buenos Aires and Berlin should show '2 days from now' for a fire date 2 calendar days away."""
        from zoneinfo import ZoneInfo

        for tz_name in ("America/Buenos_Aires", "Europe/Berlin"):
            tz = ZoneInfo(tz_name)
            local_now = datetime.now(tz)
            fire_date = (local_now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
            fire_utc = fire_date.astimezone(UTC)
            result = _format_relative(fire_utc, tz)
            assert result == "2 days from now", f"Failed for {tz_name}: got '{result}'"

    def test_one_day_from_now(self):
        """A fire time 1 calendar day away should say 'a day from now'."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Berlin")
        local_now = datetime.now(tz)
        # Don't replace the time — timedelta(days=1) guarantees ~24h delta,
        # always above the 12h threshold that triggers calendar-day formatting.
        fire_utc = (local_now + timedelta(days=1)).astimezone(UTC)
        result = _format_relative(fire_utc, tz)
        assert result == "a day from now"

    def test_no_timezone_defaults_to_utc(self):
        """With no timezone, should use UTC for calendar day calculation."""
        next_fire = datetime.now(UTC) + timedelta(days=3, hours=1)
        result = _format_relative(next_fire)
        assert result == "3 days from now"


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


class TestReminderList:
    """Tests for /reminder list timezone display."""

    @pytest.mark.asyncio
    async def test_list_shows_timezone_aware_time(self, reminder_cog, mock_interaction, db_session):
        """NextFire should be displayed in the reminder's configured timezone, not UTC."""
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="general",
            CreateDate=now,
            Author="Tester",
            ScheduleType="daily",
            ScheduleTime=time(9, 0),
            # NextFire is stored as naive UTC — 08:00 UTC = 09:00 CET (Europe/Berlin, standard time)
            NextFire=datetime(2026, 1, 15, 8, 0, 0),
            Message="Good morning",
            Count=0,
            Enabled=True,
            Timezone="Europe/Berlin",
        )
        db_session.add(r)
        db_session.commit()

        with patch("modules.reminder.send_paginated", new_callable=AsyncMock) as mock_send:
            await reminder_cog._reminder_list.callback(reminder_cog, mock_interaction)

            mock_send.assert_called_once()
            output = mock_send.call_args[0][1]  # second positional arg is the text
            # Should show 09:00 CET, not 08:00 UTC
            assert "09:00" in output
            assert "08:00 UTC" not in output

    @pytest.mark.asyncio
    async def test_list_shows_utc_for_no_timezone(self, reminder_cog, mock_interaction, db_session):
        """Reminders without a timezone should display NextFire in UTC."""
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="general",
            CreateDate=now,
            Author="Tester",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=datetime(2026, 1, 15, 14, 30, 0),
            Message="Hourly check",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()

        with patch("modules.reminder.send_paginated", new_callable=AsyncMock) as mock_send:
            await reminder_cog._reminder_list.callback(reminder_cog, mock_interaction)

            mock_send.assert_called_once()
            output = mock_send.call_args[0][1]
            assert "14:30 UTC" in output

    @pytest.mark.asyncio
    async def test_list_falls_back_to_utc_for_invalid_timezone(self, reminder_cog, mock_interaction, db_session):
        """Reminders with an invalid timezone should fall back to UTC display."""
        mock_interaction.guild.id = 123
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="general",
            CreateDate=now,
            Author="Tester",
            ScheduleType="daily",
            ScheduleTime=time(10, 0),
            NextFire=datetime(2026, 1, 15, 10, 0, 0),
            Message="Fallback test",
            Count=0,
            Enabled=True,
            Timezone="Not/A/Timezone",
        )
        db_session.add(r)
        db_session.commit()

        with patch("modules.reminder.send_paginated", new_callable=AsyncMock) as mock_send:
            await reminder_cog._reminder_list.callback(reminder_cog, mock_interaction)

            mock_send.assert_called_once()
            output = mock_send.call_args[0][1]
            assert "10:00 UTC" in output


class TestReminderEdit:
    """Tests for /reminder edit command."""

    # noinspection PyMethodMayBeStatic
    def _make_reminder(self, db_session, **overrides):
        """Helper to create a reminder with sensible defaults."""
        now = datetime.now(UTC)
        defaults = dict(
            GuildId=123,
            ChannelId=456,
            ChannelName="general",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=now + timedelta(hours=1),
            Message="Original",
            Count=0,
            Enabled=True,
        )
        defaults.update(overrides)
        r = ReminderMessage(**defaults)
        db_session.add(r)
        db_session.commit()
        return r

    @pytest.mark.asyncio
    async def test_edit_not_found(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=99999,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_nothing_to_change(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session)
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "nothing to change" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_reject_delay_on_daily(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session, ScheduleType="daily", IntervalSeconds=None, ScheduleTime=time(9, 0))
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay="2h",
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "delay" in call_args.lower()
        assert "interval" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_reject_time_of_day_on_interval(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session, ScheduleType="interval")
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day="10:00",
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "time_of_day" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_reject_day_of_week_on_daily(self, reminder_cog, mock_interaction, db_session):
        mock_interaction.guild.id = 123
        dow = MagicMock()
        dow.value = 0
        r = self._make_reminder(db_session, ScheduleType="daily", IntervalSeconds=None, ScheduleTime=time(9, 0))
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=dow,
            day_of_month=None,
            timezone=None,
        )
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "day_of_week" in call_args.lower()
        assert "weekly" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_message_only(self, reminder_cog, mock_interaction, db_session):
        """Edit only the message on an interval reminder — timing should remain unchanged."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session)
        original_next_fire = r.NextFire

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message="Updated text",
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        assert r.Message == "Updated text"
        assert r.NextFire == original_next_fire
        call_args = str(mock_interaction.response.send_message.call_args)
        assert "message" in call_args.lower()

    @pytest.mark.asyncio
    async def test_edit_channel(self, reminder_cog, mock_interaction, db_session):
        """Edit the channel — ChannelId and ChannelName should update."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session)

        new_channel = MagicMock()
        new_channel.id = 789
        new_channel.name = "announcements"
        new_channel.permissions_for = MagicMock(return_value=MagicMock(view_channel=True, send_messages=True))

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=new_channel,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        assert r.ChannelId == 789
        assert r.ChannelName == "announcements"

    @pytest.mark.asyncio
    async def test_edit_delay_recalculates(self, reminder_cog, mock_interaction, db_session):
        """Edit delay on an interval reminder — IntervalSeconds and NextFire should change."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session)  # default IntervalSeconds=3600
        original_next_fire = r.NextFire

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay="2h",
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        assert r.IntervalSeconds == 7200
        assert r.NextFire != original_next_fire

    @pytest.mark.asyncio
    async def test_edit_time_of_day_on_daily(self, reminder_cog, mock_interaction, db_session):
        """Edit time_of_day on a daily reminder — ScheduleTime should update."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session, ScheduleType="daily", IntervalSeconds=None, ScheduleTime=time(9, 0))

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day="14:30",
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        assert r.ScheduleTime.hour == 14
        assert r.ScheduleTime.minute == 30

    @pytest.mark.asyncio
    async def test_edit_timezone_on_schedule(self, reminder_cog, mock_interaction, db_session):
        """Edit timezone on a daily reminder — Timezone should update."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session, ScheduleType="daily", IntervalSeconds=None, ScheduleTime=time(9, 0))

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone="Europe/Berlin",
        )

        assert r.Timezone == "Europe/Berlin"

    @pytest.mark.asyncio
    async def test_edit_invalid_delay(self, reminder_cog, mock_interaction, db_session):
        """Edit delay with unparseable string — should return error."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(db_session)

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay="nope",
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "Could not parse" in call_args

    @pytest.mark.asyncio
    async def test_edit_invalid_day_of_month(self, reminder_cog, mock_interaction, db_session):
        """Edit day_of_month=31 on a monthly reminder — should reject with range error."""
        mock_interaction.guild.id = 123
        r = self._make_reminder(
            db_session, ScheduleType="monthly", IntervalSeconds=None, ScheduleTime=time(9, 0), ScheduleDayOfMonth=15
        )

        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            mock_interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=31,
            timezone=None,
        )

        call_args = str(mock_interaction.response.send_message.call_args)
        assert "1 and 28" in call_args


# ---------------------------------------------------------------------------
# Localization tests for reminder commands
# ---------------------------------------------------------------------------


@pytest.fixture
def _load_locale_strings():
    load_strings()


def _set_german(db_session):
    db_session.add(GuildLanguageConfig(GuildId=123, Language="de"))
    db_session.commit()


def _interaction_for_reminder(mock_interaction):
    """Configure an interaction with guild_id=123 and channel permissions."""
    mock_interaction.guild.id = 123
    mock_interaction.guild_id = 123
    mock_interaction.channel.id = 456
    mock_interaction.channel.name = "general"
    mock_interaction.channel.permissions_for = MagicMock(return_value=MagicMock(view_channel=True, send_messages=True))
    return mock_interaction


class TestReminderCreateLocale:
    async def test_create_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
        await reminder_cog._reminder_create.callback(
            reminder_cog, interaction, delay="2h", message="Test", channel=None, repeat=False
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "Reminder created" in msg

    async def test_create_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        await reminder_cog._reminder_create.callback(
            reminder_cog, interaction, delay="2h", message="Test", channel=None, repeat=False
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "Erinnerung erstellt" in msg


class TestReminderScheduleLocale:
    async def test_invalid_time_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
        stype = MagicMock()
        stype.value = "daily"
        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            interaction,
            schedule_type=stype,
            time_of_day="bad",
            message="Test",
            channel=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "Invalid time format" in msg

    async def test_invalid_time_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        stype = MagicMock()
        stype.value = "daily"
        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            interaction,
            schedule_type=stype,
            time_of_day="bad",
            message="Test",
            channel=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "Ungültiges Zeitformat" in msg

    async def test_day_of_week_required_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        stype = MagicMock()
        stype.value = "weekly"
        await reminder_cog._reminder_schedule.callback(
            reminder_cog,
            interaction,
            schedule_type=stype,
            time_of_day="09:00",
            message="Test",
            channel=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "wöchentliche Erinnerungen" in msg


class TestReminderListLocale:
    async def test_no_reminders_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
        await reminder_cog._reminder_list.callback(reminder_cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "No reminders set" in msg

    async def test_no_reminders_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        await reminder_cog._reminder_list.callback(reminder_cog, interaction)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Keine Erinnerungen gesetzt" in msg


class TestReminderDeleteLocale:
    async def test_delete_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="once",
            NextFire=now + timedelta(hours=1),
            Message="X",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()
        await reminder_cog._reminder_delete.callback(reminder_cog, interaction, reminder_id=r.Id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Message deleted" in msg

    async def test_delete_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=456,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="once",
            NextFire=now + timedelta(hours=1),
            Message="X",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()
        await reminder_cog._reminder_delete.callback(reminder_cog, interaction, reminder_id=r.Id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nachricht gelöscht" in msg


class TestReminderPauseLocale:
    async def test_already_paused_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
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
            Message="X",
            Count=0,
            Enabled=False,
        )
        db_session.add(r)
        db_session.commit()
        await reminder_cog._reminder_pause.callback(reminder_cog, interaction, reminder_id=r.Id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "already paused" in msg

    async def test_already_paused_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
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
            Message="X",
            Count=0,
            Enabled=False,
        )
        db_session.add(r)
        db_session.commit()
        await reminder_cog._reminder_pause.callback(reminder_cog, interaction, reminder_id=r.Id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "bereits pausiert" in msg


class TestReminderResumeLocale:
    async def test_already_active_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
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
            Message="X",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()
        await reminder_cog._reminder_resume.callback(reminder_cog, interaction, reminder_id=r.Id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "already active" in msg

    async def test_already_active_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
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
            Message="X",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()
        await reminder_cog._reminder_resume.callback(reminder_cog, interaction, reminder_id=r.Id)
        msg = interaction.response.send_message.call_args[0][0]
        assert "bereits aktiv" in msg


class TestReminderEditLocale:
    # noinspection PyMethodMayBeStatic
    def _make_reminder(self, db_session, **overrides):
        now = datetime.now(UTC)
        defaults = dict(
            GuildId=123,
            ChannelId=456,
            ChannelName="general",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=now + timedelta(hours=1),
            Message="Original",
            Count=0,
            Enabled=True,
        )
        defaults.update(overrides)
        r = ReminderMessage(**defaults)
        db_session.add(r)
        db_session.commit()
        return r

    async def test_nothing_to_change_english(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        interaction = _interaction_for_reminder(mock_interaction)
        r = self._make_reminder(db_session)
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nothing to change" in msg

    async def test_nothing_to_change_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        r = self._make_reminder(db_session)
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay=None,
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "Nichts zu ändern" in msg

    async def test_param_not_applicable_german(self, _load_locale_strings, reminder_cog, mock_interaction, db_session):
        _set_german(db_session)
        interaction = _interaction_for_reminder(mock_interaction)
        r = self._make_reminder(db_session, ScheduleType="daily", IntervalSeconds=None, ScheduleTime=time(9, 0))
        await reminder_cog._reminder_edit.callback(
            reminder_cog,
            interaction,
            reminder_id=r.Id,
            message=None,
            channel=None,
            delay="2h",
            time_of_day=None,
            day_of_week=None,
            day_of_month=None,
            timezone=None,
        )
        msg = interaction.response.send_message.call_args[0][0]
        assert "gilt nur für" in msg


class TestFormatRelativeLocale:
    def test_a_day_german(self, _load_locale_strings):
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Berlin")
        local_now = datetime.now(tz)
        fire_utc = (local_now + timedelta(days=1)).astimezone(UTC)
        result = _format_relative(fire_utc, tz, lang="de")
        assert result == "in einem Tag"

    def test_days_german(self, _load_locale_strings):
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Berlin")
        local_now = datetime.now(tz)
        fire_date = (local_now + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
        fire_utc = fire_date.astimezone(UTC)
        result = _format_relative(fire_utc, tz, lang="de")
        assert result == "in 3 Tagen"
