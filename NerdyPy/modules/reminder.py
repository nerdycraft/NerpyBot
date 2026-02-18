# NerdyPy/modules/reminder.py
# -*- coding: utf-8 -*-

from datetime import UTC, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo, available_timezones

import humanize
from discord import Interaction, TextChannel, app_commands
from discord.ext import tasks
from discord.ext.commands import GroupCog
from models.reminder import ReminderMessage
from utils.duration import parse_duration
from utils.helpers import notify_error, send_paginated
from utils.permissions import validate_channel_permissions
from utils.schedule import compute_next_fire

LOOP_MAX_SECONDS = 60
LOOP_MIN_SECONDS = 5

WEEKDAY_MAP = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}

# Pre-sorted timezone list for autocomplete
_TZ_NAMES = sorted(available_timezones())


@app_commands.guild_only()
class Reminder(GroupCog, group_name="reminder"):
    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")
        self.bot = bot
        self._reminder_loop.start()

    def cog_unload(self):
        self._reminder_loop.cancel()

    # -- Smart loop ----------------------------------------------------

    @tasks.loop(seconds=LOOP_MAX_SECONDS)
    async def _reminder_loop(self):
        self.bot.log.debug("Reminder loop tick")
        try:
            with self.bot.session_scope() as session:
                due = ReminderMessage.get_due(session)
                self.bot.log.debug(f"Found {len(due)} due reminder(s)")

                for msg in due:
                    try:
                        await self._fire_reminder(msg, session)
                    except Exception as ex:
                        self.bot.log.error(f"Reminder #{msg.Id} fire failed: {ex}")
                        await notify_error(self.bot, f"Reminder #{msg.Id} fire", ex)

                # Adjust interval to next due reminder
                next_fire = ReminderMessage.get_next_fire_time(session)

            self._adjust_interval(next_fire)

        except Exception as ex:
            self.bot.log.error(f"Reminder loop: {ex}")
            await notify_error(self.bot, "Reminder background loop", ex)

    async def _fire_reminder(self, msg: ReminderMessage, session):
        """Send a reminder message and handle rescheduling or deletion."""
        guild = self.bot.get_guild(msg.GuildId)
        if guild is None:
            session.delete(msg)
            return

        chan = guild.get_channel(msg.ChannelId)
        if chan is None:
            session.delete(msg)
            return

        await chan.send(msg.Message)
        msg.Count += 1

        tz = None
        if msg.Timezone:
            try:
                tz = ZoneInfo(msg.Timezone)
            except (KeyError, ValueError):
                self.bot.log.warning(f"Reminder #{msg.Id}: invalid timezone '{msg.Timezone}', falling back to UTC")
                tz = None
        next_fire = compute_next_fire(
            msg.ScheduleType,
            interval_seconds=msg.IntervalSeconds,
            schedule_time=msg.ScheduleTime,
            schedule_day_of_week=msg.ScheduleDayOfWeek,
            schedule_day_of_month=msg.ScheduleDayOfMonth,
            timezone=tz,
        )

        if next_fire is None:
            session.delete(msg)
        else:
            msg.NextFire = next_fire

    def _adjust_interval(self, next_fire: datetime | None):
        """Adjust the loop interval based on the next due reminder."""
        if next_fire is None:
            seconds = LOOP_MAX_SECONDS
        else:
            delta = (next_fire - datetime.now(UTC)).total_seconds()
            seconds = max(LOOP_MIN_SECONDS, min(delta, LOOP_MAX_SECONDS))
        self._reminder_loop.change_interval(seconds=seconds)

    def _reschedule(self):
        """Restart the loop so it immediately re-evaluates timing."""
        self._reminder_loop.restart()

    @_reminder_loop.before_loop
    async def _reminder_before_loop(self):
        self.bot.log.info("Reminder: Waiting for Bot to be ready...")
        await self.bot.wait_until_ready()

    # -- /reminder create ----------------------------------------------

    @app_commands.command(name="create")
    @app_commands.describe(
        duration="Delay before firing, e.g. 2h30m, 1d, 90s, 1w (minimum 60s)",
        message="Message text to send",
        channel="Target channel (defaults to current)",
        repeat="Repeat at the same interval (default: no)",
        start="Start time as duration offset or ISO datetime (default: now + duration)",
    )
    async def _reminder_create(
        self,
        interaction: Interaction,
        duration: str,
        message: str,
        channel: Optional[TextChannel] = None,
        repeat: bool = False,
        start: Optional[str] = None,
    ):
        """Create an interval-based reminder."""
        try:
            td = parse_duration(duration)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        target = channel or interaction.channel
        validate_channel_permissions(target, interaction.guild, "view_channel", "send_messages")

        interval_seconds = int(td.total_seconds()) if repeat else None
        schedule_type = "interval" if repeat else "once"

        if start:
            try:
                # Try ISO datetime first
                next_fire = datetime.fromisoformat(start).astimezone(UTC)
            except ValueError:
                # Try as duration offset
                try:
                    start_td = parse_duration(start)
                    next_fire = datetime.now(UTC) + start_td
                except ValueError as e:
                    await interaction.response.send_message(f"Invalid start: {e}", ephemeral=True)
                    return
        else:
            next_fire = datetime.now(UTC) + td

        with self.bot.session_scope() as session:
            reminder = ReminderMessage(
                GuildId=interaction.guild.id,
                ChannelId=target.id,
                ChannelName=target.name,
                Author=str(interaction.user),
                CreateDate=datetime.now(UTC),
                NextFire=next_fire,
                ScheduleType=schedule_type,
                IntervalSeconds=interval_seconds,
                Message=message,
                Count=0,
                Enabled=True,
            )
            session.add(reminder)

        self._reschedule()
        rel = humanize.naturaltime(next_fire, when=datetime.now(UTC))
        await interaction.response.send_message(f"Reminder created — next fire {rel}.", ephemeral=True)

    # -- /reminder schedule --------------------------------------------

    @app_commands.command(name="schedule")
    @app_commands.describe(
        schedule_type="Schedule type: daily, weekly, or monthly",
        time_of_day="Time of day in HH:MM (24h format)",
        message="Message text to send",
        channel="Target channel (defaults to current)",
        day_of_week="Day of week (required for weekly)",
        day_of_month="Day of month 1-28 (required for monthly)",
        timezone="IANA timezone, e.g. Europe/Berlin (default: UTC)",
    )
    @app_commands.choices(
        schedule_type=[
            app_commands.Choice(name="Daily", value="daily"),
            app_commands.Choice(name="Weekly", value="weekly"),
            app_commands.Choice(name="Monthly", value="monthly"),
        ],
        day_of_week=[app_commands.Choice(name=name, value=val) for name, val in WEEKDAY_MAP.items()],
    )
    async def _reminder_schedule(
        self,
        interaction: Interaction,
        schedule_type: app_commands.Choice[str],
        time_of_day: str,
        message: str,
        channel: Optional[TextChannel] = None,
        day_of_week: Optional[app_commands.Choice[int]] = None,
        day_of_month: Optional[int] = None,
        timezone: Optional[str] = None,
    ):
        """Create a calendar-based reminder (daily, weekly, monthly)."""
        # Parse time
        try:
            parts = time_of_day.split(":")
            sched_time = time(int(parts[0]), int(parts[1]))
        except (ValueError, IndexError):
            await interaction.response.send_message("Invalid time format. Use HH:MM (e.g. 09:00).", ephemeral=True)
            return

        # Validate timezone
        tz = None
        if timezone:
            try:
                tz = ZoneInfo(timezone)
            except (KeyError, ValueError):
                await interaction.response.send_message(f"Unknown timezone: {timezone}", ephemeral=True)
                return

        stype = schedule_type.value

        # Validate required fields per schedule type
        dow = None
        dom = None
        if stype == "weekly":
            if day_of_week is None:
                await interaction.response.send_message("day_of_week is required for weekly schedules.", ephemeral=True)
                return
            dow = day_of_week.value
        elif stype == "monthly":
            if day_of_month is None:
                await interaction.response.send_message(
                    "day_of_month is required for monthly schedules.", ephemeral=True
                )
                return
            if not 1 <= day_of_month <= 28:
                await interaction.response.send_message("day_of_month must be between 1 and 28.", ephemeral=True)
                return
            dom = day_of_month

        target = channel or interaction.channel
        validate_channel_permissions(target, interaction.guild, "view_channel", "send_messages")

        next_fire = compute_next_fire(
            stype,
            schedule_time=sched_time,
            schedule_day_of_week=dow,
            schedule_day_of_month=dom,
            timezone=tz,
        )

        with self.bot.session_scope() as session:
            reminder = ReminderMessage(
                GuildId=interaction.guild.id,
                ChannelId=target.id,
                ChannelName=target.name,
                Author=str(interaction.user),
                CreateDate=datetime.now(UTC),
                NextFire=next_fire,
                ScheduleType=stype,
                ScheduleTime=sched_time,
                ScheduleDayOfWeek=dow,
                ScheduleDayOfMonth=dom,
                Timezone=timezone,
                Message=message,
                Count=0,
                Enabled=True,
            )
            session.add(reminder)

        self._reschedule()
        rel = humanize.naturaltime(next_fire, when=datetime.now(UTC))
        await interaction.response.send_message(f"Scheduled reminder created — next fire {rel}.", ephemeral=True)

    async def _timezone_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
        current_lower = current.lower()
        return [app_commands.Choice(name=tz, value=tz) for tz in _TZ_NAMES if current_lower in tz.lower()][:25]

    _reminder_schedule = app_commands.autocomplete(timezone=_timezone_autocomplete)(_reminder_schedule)

    # -- /reminder list ------------------------------------------------

    @app_commands.command(name="list")
    async def _reminder_list(self, interaction: Interaction):
        """List all current reminder messages."""
        with self.bot.session_scope() as session:
            msgs = ReminderMessage.get_all_by_guild(interaction.guild.id, session)
            if not msgs:
                await interaction.response.send_message("No reminders set.", ephemeral=True)
                return

            to_send = ""
            for msg in msgs:
                status = "\u2705" if msg.Enabled else "\u23f8\ufe0f"
                if msg.Enabled:
                    next_fire = msg.NextFire.replace(tzinfo=UTC)
                    rel = humanize.naturaltime(next_fire, when=datetime.now(UTC))
                    abs_time = next_fire.strftime("%Y-%m-%d %H:%M UTC")
                    timing = f"Next: {rel} ({abs_time})"
                else:
                    timing = "paused"

                schedule_info = msg.ScheduleType
                if msg.ScheduleType == "once":
                    schedule_info = "one-time"
                elif msg.ScheduleType == "interval" and msg.IntervalSeconds:
                    schedule_info = f"every {humanize.naturaldelta(timedelta(seconds=msg.IntervalSeconds))}"
                elif msg.ScheduleType == "daily" and msg.ScheduleTime:
                    tz_label = msg.Timezone or "UTC"
                    schedule_info = f"daily at {msg.ScheduleTime.strftime('%H:%M')} {tz_label}"
                elif (
                    msg.ScheduleType == "weekly" and msg.ScheduleTime is not None and msg.ScheduleDayOfWeek is not None
                ):
                    day_name = list(WEEKDAY_MAP.keys())[msg.ScheduleDayOfWeek]
                    tz_label = msg.Timezone or "UTC"
                    schedule_info = f"weekly {day_name} at {msg.ScheduleTime.strftime('%H:%M')} {tz_label}"
                elif (
                    msg.ScheduleType == "monthly"
                    and msg.ScheduleTime is not None
                    and msg.ScheduleDayOfMonth is not None
                ):
                    tz_label = msg.Timezone or "UTC"
                    schedule_info = (
                        f"monthly day {msg.ScheduleDayOfMonth} at {msg.ScheduleTime.strftime('%H:%M')} {tz_label}"
                    )

                to_send += f"{status} **#{msg.Id}** \u2014 #{msg.ChannelName} \u2014 {schedule_info}\n"
                to_send += f"> {msg.Message}\n"
                to_send += f"*{msg.Author} \u00b7 {timing} \u00b7 Hits: {msg.Count}*\n\n"

            await send_paginated(interaction, to_send, title="\u23f0 Reminders", color=0xF39C12, ephemeral=True)

    # -- Autocomplete helper -------------------------------------------

    async def _reminder_id_autocomplete(self, interaction: Interaction, current: str) -> list[app_commands.Choice[int]]:
        with self.bot.session_scope() as session:
            reminders = ReminderMessage.get_all_by_guild(interaction.guild.id, session)
            choices = []
            for msg in reminders:
                status = "\u2705" if msg.Enabled else "\u23f8\ufe0f"
                label = f"#{msg.Id} {status} {msg.Message[:80]}"
                if current and current not in str(msg.Id) and current.lower() not in msg.Message.lower():
                    continue
                choices.append(app_commands.Choice(name=label[:100], value=msg.Id))
            return choices[:25]

    # -- /reminder delete ----------------------------------------------

    @app_commands.command(name="delete")
    @app_commands.autocomplete(reminder_id=_reminder_id_autocomplete)
    async def _reminder_delete(self, interaction: Interaction, reminder_id: int):
        """Delete a reminder message."""
        with self.bot.session_scope() as session:
            ReminderMessage.delete(reminder_id, interaction.guild.id, session)
        self._reschedule()
        await interaction.response.send_message("Message deleted.", ephemeral=True)

    # -- /reminder pause -----------------------------------------------

    @app_commands.command(name="pause")
    @app_commands.autocomplete(reminder_id=_reminder_id_autocomplete)
    async def _reminder_pause(self, interaction: Interaction, reminder_id: int):
        """Pause a reminder without deleting it."""
        with self.bot.session_scope() as session:
            msg = ReminderMessage.get_by_id(reminder_id, interaction.guild.id, session)
            if msg is None:
                await interaction.response.send_message("Reminder not found.", ephemeral=True)
                return
            if not msg.Enabled:
                await interaction.response.send_message("Reminder is already paused.", ephemeral=True)
                return
            msg.Enabled = False
        self._reschedule()
        await interaction.response.send_message(f"Paused reminder **#{reminder_id}**.", ephemeral=True)

    # -- /reminder resume ----------------------------------------------

    @app_commands.command(name="resume")
    @app_commands.autocomplete(reminder_id=_reminder_id_autocomplete)
    async def _reminder_resume(self, interaction: Interaction, reminder_id: int):
        """Resume a paused reminder."""
        with self.bot.session_scope() as session:
            msg = ReminderMessage.get_by_id(reminder_id, interaction.guild.id, session)
            if msg is None:
                await interaction.response.send_message("Reminder not found.", ephemeral=True)
                return
            if msg.Enabled:
                await interaction.response.send_message("Reminder is already active.", ephemeral=True)
                return
            msg.Enabled = True
            # Recalculate NextFire if it's in the past
            if msg.NextFire.replace(tzinfo=UTC) < datetime.now(UTC):
                tz = ZoneInfo(msg.Timezone) if msg.Timezone else None
                next_fire = compute_next_fire(
                    msg.ScheduleType,
                    interval_seconds=msg.IntervalSeconds,
                    schedule_time=msg.ScheduleTime,
                    schedule_day_of_week=msg.ScheduleDayOfWeek,
                    schedule_day_of_month=msg.ScheduleDayOfMonth,
                    timezone=tz,
                )
                if next_fire is not None:
                    msg.NextFire = next_fire
                else:
                    # One-shot whose time has passed — just delete it
                    session.delete(msg)
                    await interaction.response.send_message(
                        f"Reminder **#{reminder_id}** expired while paused and has been deleted.", ephemeral=True
                    )
                    self._reschedule()
                    return
        self._reschedule()
        await interaction.response.send_message(f"Resumed reminder **#{reminder_id}**.", ephemeral=True)


async def setup(bot):
    """adds this module to the bot"""
    await bot.add_cog(Reminder(bot))
