# -*- coding: utf-8 -*-
"""Tests for models/reminder.py - ReminderMessage model"""

from datetime import UTC, datetime


from models.reminder import ReminderMessage


class TestReminderMessageGetById:
    """Tests for ReminderMessage.get_by_id() class method."""

    def test_get_existing_reminder(self, db_session):
        """Should return reminder by ID and guild."""
        # Setup
        reminder = ReminderMessage(
            GuildId=123456789,
            ChannelId=111222333,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            Repeat=0,
            Minutes=60,
            LastSend=datetime.now(UTC),
            Message="Test reminder",
            Count=0,
        )
        db_session.add(reminder)
        db_session.commit()

        # Get the auto-generated ID
        reminder_id = reminder.Id

        # Test
        result = ReminderMessage.get_by_id(reminder_id, 123456789, db_session)

        assert result is not None
        assert result.Id == reminder_id
        assert result.Message == "Test reminder"

    def test_get_nonexistent_id_returns_none(self, db_session):
        """Should return None for non-existent ID."""
        result = ReminderMessage.get_by_id(99999, 123456789, db_session)
        assert result is None

    def test_get_wrong_guild_returns_none(self, db_session):
        """Should return None when guild doesn't match."""
        # Setup
        reminder = ReminderMessage(
            GuildId=123456789,
            ChannelId=111222333,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            Repeat=0,
            Minutes=60,
            LastSend=datetime.now(UTC),
            Message="Test reminder",
            Count=0,
        )
        db_session.add(reminder)
        db_session.commit()

        # Test with wrong guild
        result = ReminderMessage.get_by_id(reminder.Id, 999999999, db_session)
        assert result is None


class TestReminderMessageGetAllByGuild:
    """Tests for ReminderMessage.get_all_by_guild() class method."""

    def test_get_all_for_guild(self, db_session):
        """Should return all reminders for a guild."""
        # Setup - 3 reminders for guild 123
        for i in range(3):
            reminder = ReminderMessage(
                GuildId=123,
                ChannelId=111,
                ChannelName=f"channel-{i}",
                CreateDate=datetime.now(UTC),
                Author="TestUser",
                Repeat=0,
                Minutes=60,
                LastSend=datetime.now(UTC),
                Message=f"Reminder {i}",
                Count=0,
            )
            db_session.add(reminder)
        db_session.commit()

        # Test
        results = ReminderMessage.get_all_by_guild(123, db_session)
        assert len(results) == 3

    def test_get_all_excludes_other_guilds(self, db_session):
        """Should only return reminders for specified guild."""
        # Setup - reminders for different guilds
        for guild_id in [111, 111, 222, 333]:
            reminder = ReminderMessage(
                GuildId=guild_id,
                ChannelId=111,
                ChannelName="general",
                CreateDate=datetime.now(UTC),
                Author="TestUser",
                Repeat=0,
                Minutes=60,
                LastSend=datetime.now(UTC),
                Message="Test",
                Count=0,
            )
            db_session.add(reminder)
        db_session.commit()

        # Test
        results = ReminderMessage.get_all_by_guild(111, db_session)
        assert len(results) == 2

    def test_get_all_empty_guild(self, db_session):
        """Should return empty list for guild with no reminders."""
        results = ReminderMessage.get_all_by_guild(999999999, db_session)
        assert len(results) == 0


class TestReminderMessageDelete:
    """Tests for ReminderMessage.delete() class method."""

    def test_delete_existing_reminder(self, db_session):
        """Should remove reminder from database."""
        # Setup
        reminder = ReminderMessage(
            GuildId=123456789,
            ChannelId=111222333,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            Repeat=0,
            Minutes=60,
            LastSend=datetime.now(UTC),
            Message="To be deleted",
            Count=0,
        )
        db_session.add(reminder)
        db_session.commit()
        reminder_id = reminder.Id

        # Test
        ReminderMessage.delete(reminder_id, 123456789, db_session)
        db_session.commit()

        # Verify
        assert ReminderMessage.get_by_id(reminder_id, 123456789, db_session) is None


class TestReminderMessageStr:
    """Tests for ReminderMessage.__str__() method."""

    def test_str_contains_author(self, db_session):
        """String representation should contain author."""
        reminder = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestAuthor",
            Repeat=0,
            Minutes=60,
            LastSend=datetime.now(UTC),
            Message="Test",
            Count=5,
        )
        db_session.add(reminder)
        db_session.commit()

        result = str(reminder)
        assert "TestAuthor" in result

    def test_str_contains_channel(self, db_session):
        """String representation should contain channel."""
        reminder = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="test-channel",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            Repeat=0,
            Minutes=60,
            LastSend=datetime.now(UTC),
            Message="Test",
            Count=0,
        )
        db_session.add(reminder)
        db_session.commit()

        result = str(reminder)
        assert "test-channel" in result

    def test_str_contains_count(self, db_session):
        """String representation should contain hit count."""
        reminder = ReminderMessage(
            GuildId=123,
            ChannelId=111,
            ChannelName="general",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
            Repeat=0,
            Minutes=60,
            LastSend=datetime.now(UTC),
            Message="Test",
            Count=42,
        )
        db_session.add(reminder)
        db_session.commit()

        result = str(reminder)
        assert "42" in result


class TestReminderMessageGetAll:
    """Tests for ReminderMessage.get_all() class method."""

    def test_get_all_returns_all_reminders(self, db_session):
        """Should return all reminders across all guilds."""
        # Setup - reminders for different guilds
        for guild_id in [111, 222, 333]:
            reminder = ReminderMessage(
                GuildId=guild_id,
                ChannelId=111,
                ChannelName="general",
                CreateDate=datetime.now(UTC),
                Author="TestUser",
                Repeat=0,
                Minutes=60,
                LastSend=datetime.now(UTC),
                Message="Test",
                Count=0,
            )
            db_session.add(reminder)
        db_session.commit()

        # Test
        results = ReminderMessage.get_all(db_session)
        assert len(results) == 3

    def test_get_all_ordered_by_id(self, db_session):
        """Results should be ordered by ID ascending."""
        # Create in reverse order
        for guild_id in [333, 222, 111]:
            reminder = ReminderMessage(
                GuildId=guild_id,
                ChannelId=111,
                ChannelName="general",
                CreateDate=datetime.now(UTC),
                Author="TestUser",
                Repeat=0,
                Minutes=60,
                LastSend=datetime.now(UTC),
                Message="Test",
                Count=0,
            )
            db_session.add(reminder)
        db_session.commit()

        # Test
        results = ReminderMessage.get_all(db_session)

        # IDs should be in ascending order
        ids = [r.Id for r in results]
        assert ids == sorted(ids)
