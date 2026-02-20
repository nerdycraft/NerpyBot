# tests/models/test_reminder.py
# -*- coding: utf-8 -*-
"""Tests for models/reminder.py - ReminderMessage model (rewritten schema)."""

from datetime import UTC, datetime, time, timedelta

from models.reminder import ReminderMessage


class TestReminderMessageGetById:
    """Tests for ReminderMessage.get_by_id()."""

    def test_get_existing(self, db_session):
        reminder = ReminderMessage(
            GuildId=123456789,
            ChannelId=111222333,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=datetime.now(UTC) + timedelta(hours=1),
            Message="Test reminder",
            Count=0,
        )
        db_session.add(reminder)
        db_session.commit()

        result = ReminderMessage.get_by_id(reminder.Id, 123456789, db_session)
        assert result is not None
        assert result.Message == "Test reminder"
        assert result.ScheduleType == "interval"
        assert result.IntervalSeconds == 3600

    def test_get_nonexistent_returns_none(self, db_session):
        assert ReminderMessage.get_by_id(99999, 123456789, db_session) is None

    def test_get_wrong_guild_returns_none(self, db_session):
        reminder = ReminderMessage(
            GuildId=123456789,
            ChannelId=111222333,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            ScheduleType="once",
            NextFire=datetime.now(UTC) + timedelta(hours=1),
            Message="Test",
            Count=0,
        )
        db_session.add(reminder)
        db_session.commit()
        assert ReminderMessage.get_by_id(reminder.Id, 999999999, db_session) is None


class TestReminderMessageGetDue:
    """Tests for ReminderMessage.get_due()."""

    def test_returns_only_due_and_enabled(self, db_session):
        now = datetime.now(UTC)
        # noinspection GrazieInspection
        # Due and enabled
        r1 = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=60,
            NextFire=now - timedelta(seconds=10),
            Message="due",
            Count=0,
            Enabled=True,
        )
        # noinspection GrazieInspection
        # Due but disabled
        r2 = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=60,
            NextFire=now - timedelta(seconds=10),
            Message="disabled",
            Count=0,
            Enabled=False,
        )
        # Not yet due
        r3 = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=now + timedelta(hours=1),
            Message="future",
            Count=0,
            Enabled=True,
        )
        db_session.add_all([r1, r2, r3])
        db_session.commit()

        results = ReminderMessage.get_due(db_session)
        assert len(results) == 1
        assert results[0].Message == "due"

    def test_returns_empty_when_none_due(self, db_session):
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="once",
            NextFire=now + timedelta(hours=1),
            Message="future",
            Count=0,
            Enabled=True,
        )
        db_session.add(r)
        db_session.commit()
        assert ReminderMessage.get_due(db_session) == []


class TestReminderMessageGetNextFireTime:
    """Tests for ReminderMessage.get_next_fire_time()."""

    def test_returns_earliest_next_fire(self, db_session):
        now = datetime.now(UTC)
        soon = now + timedelta(minutes=5)
        later = now + timedelta(hours=2)

        for nf in [later, soon]:  # insert out of order
            r = ReminderMessage(
                GuildId=123,
                ChannelId=111,
                ChannelName="ch",
                CreateDate=now,
                Author="A",
                ScheduleType="interval",
                IntervalSeconds=60,
                NextFire=nf,
                Message="msg",
                Count=0,
                Enabled=True,
            )
            db_session.add(r)
        db_session.commit()

        result = ReminderMessage.get_next_fire_time(db_session)
        # Compare with 1s tolerance for test timing
        assert abs((result - soon).total_seconds()) < 2

    def test_returns_none_when_no_enabled(self, db_session):
        assert ReminderMessage.get_next_fire_time(db_session) is None


class TestReminderMessageGetAllByGuild:
    """Tests for ReminderMessage.get_all_by_guild()."""

    def test_returns_all_for_guild(self, db_session):
        now = datetime.now(UTC)
        for i in range(3):
            db_session.add(
                ReminderMessage(
                    GuildId=123,
                    ChannelId=111,
                    ChannelName=f"ch-{i}",
                    CreateDate=now,
                    Author="A",
                    ScheduleType="once",
                    NextFire=now + timedelta(hours=1),
                    Message=f"msg-{i}",
                    Count=0,
                )
            )
        db_session.commit()
        assert len(ReminderMessage.get_all_by_guild(123, db_session)) == 3

    def test_excludes_other_guilds(self, db_session):
        now = datetime.now(UTC)
        for gid in [111, 111, 222]:
            db_session.add(
                ReminderMessage(
                    GuildId=gid,
                    ChannelId=111,
                    ChannelName="ch",
                    CreateDate=now,
                    Author="A",
                    ScheduleType="once",
                    NextFire=now + timedelta(hours=1),
                    Message="msg",
                    Count=0,
                )
            )
        db_session.commit()
        assert len(ReminderMessage.get_all_by_guild(111, db_session)) == 2


class TestReminderMessageDelete:
    """Tests for ReminderMessage.delete()."""

    def test_delete_existing(self, db_session):
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="once",
            NextFire=now + timedelta(hours=1),
            Message="gone",
            Count=0,
        )
        db_session.add(r)
        db_session.commit()
        rid = r.Id

        ReminderMessage.delete(rid, 123, db_session)
        db_session.commit()
        assert ReminderMessage.get_by_id(rid, 123, db_session) is None


class TestReminderMessageStr:
    """Tests for ReminderMessage.__str__() method."""

    def test_str_contains_key_fields(self, db_session):
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="test-channel",
            CreateDate=now,
            Author="TestAuthor",
            ScheduleType="interval",
            IntervalSeconds=3600,
            NextFire=now + timedelta(hours=1),
            Message="Test message",
            Count=5,
        )
        db_session.add(r)
        db_session.commit()

        result = str(r)
        assert "TestAuthor" in result
        assert "test-channel" in result
        assert "interval" in result
        assert "Test message" in result
        assert "5" in result


class TestReminderMessageScheduleFields:
    """Tests for calendar-schedule columns."""

    def test_daily_schedule_fields(self, db_session):
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="daily",
            ScheduleTime=time(9, 0),
            Timezone="Europe/Berlin",
            NextFire=now + timedelta(hours=1),
            Message="daily",
            Count=0,
        )
        db_session.add(r)
        db_session.commit()

        result = ReminderMessage.get_by_id(r.Id, 123, db_session)
        assert result.ScheduleType == "daily"
        assert result.ScheduleTime == time(9, 0)
        assert result.Timezone == "Europe/Berlin"
        assert result.ScheduleDayOfWeek is None

    def test_weekly_schedule_fields(self, db_session):
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="weekly",
            ScheduleTime=time(9, 0),
            ScheduleDayOfWeek=0,
            NextFire=now + timedelta(days=1),
            Message="weekly",
            Count=0,
        )
        db_session.add(r)
        db_session.commit()

        result = ReminderMessage.get_by_id(r.Id, 123, db_session)
        assert result.ScheduleDayOfWeek == 0

    def test_monthly_schedule_fields(self, db_session):
        now = datetime.now(UTC)
        r = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="ch",
            CreateDate=now,
            Author="A",
            ScheduleType="monthly",
            ScheduleTime=time(12, 0),
            ScheduleDayOfMonth=15,
            NextFire=now + timedelta(days=10),
            Message="monthly",
            Count=0,
        )
        db_session.add(r)
        db_session.commit()

        result = ReminderMessage.get_by_id(r.Id, 123, db_session)
        assert result.ScheduleDayOfMonth == 15
