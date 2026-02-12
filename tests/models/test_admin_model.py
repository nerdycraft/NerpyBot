# -*- coding: utf-8 -*-
"""Tests for models/admin.py - GuildPrefix model"""

from datetime import UTC, datetime

import pytest

from models.admin import GuildPrefix


class TestGuildPrefixGet:
    """Tests for GuildPrefix.get() class method."""

    def test_get_existing_prefix(self, db_session):
        """Should return prefix for existing guild."""
        # Setup
        prefix = GuildPrefix(
            GuildId=123456789,
            Prefix=">>",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
        )
        db_session.add(prefix)
        db_session.commit()

        # Test
        result = GuildPrefix.get(123456789, db_session)

        assert result is not None
        assert result.GuildId == 123456789
        assert result.Prefix == ">>"

    def test_get_nonexistent_prefix_returns_none(self, db_session):
        """Should return None for guild without prefix."""
        result = GuildPrefix.get(999999999, db_session)
        assert result is None

    def test_get_correct_guild_with_multiple_prefixes(self, db_session):
        """Should return correct prefix when multiple guilds exist."""
        # Setup multiple prefixes
        for guild_id, prefix in [(111, "!"), (222, "?"), (333, ">>")]:
            p = GuildPrefix(
                GuildId=guild_id,
                Prefix=prefix,
                CreateDate=datetime.now(UTC),
                Author="TestUser",
            )
            db_session.add(p)
        db_session.commit()

        # Test
        result = GuildPrefix.get(222, db_session)
        assert result.Prefix == "?"


class TestGuildPrefixDelete:
    """Tests for GuildPrefix.delete() class method."""

    def test_delete_existing_prefix(self, db_session):
        """Should remove prefix from database."""
        # Setup
        prefix = GuildPrefix(
            GuildId=123456789,
            Prefix=">>",
            CreateDate=datetime.now(UTC),
            Author="TestUser",
        )
        db_session.add(prefix)
        db_session.commit()

        # Test
        GuildPrefix.delete(123456789, db_session)
        db_session.commit()

        # Verify
        assert GuildPrefix.get(123456789, db_session) is None

    def test_delete_nonexistent_raises_error(self, db_session):
        """Should raise error when deleting non-existent prefix."""
        with pytest.raises(Exception):  # SQLAlchemy will raise when deleting None
            GuildPrefix.delete(999999999, db_session)


class TestGuildPrefixCreate:
    """Tests for creating GuildPrefix entries."""

    def test_create_new_prefix(self, db_session):
        """Should save new prefix to database."""
        prefix = GuildPrefix(
            GuildId=123456789,
            Prefix="!",
            CreateDate=datetime.now(UTC),
            Author="Creator",
        )
        db_session.add(prefix)
        db_session.commit()

        # Verify
        retrieved = GuildPrefix.get(123456789, db_session)
        assert retrieved is not None
        assert retrieved.Prefix == "!"
        assert retrieved.Author == "Creator"

    def test_prefix_fields_stored_correctly(self, db_session):
        """All fields should be stored and retrieved correctly."""
        now = datetime.now(UTC)
        prefix = GuildPrefix(
            GuildId=123456789,
            Prefix=">>",
            CreateDate=now,
            ModifiedDate=now,
            Author="TestAuthor",
        )
        db_session.add(prefix)
        db_session.commit()

        # Verify all fields
        retrieved = GuildPrefix.get(123456789, db_session)
        assert retrieved.GuildId == 123456789
        assert retrieved.Prefix == ">>"
        assert retrieved.Author == "TestAuthor"
        assert retrieved.CreateDate is not None
        assert retrieved.ModifiedDate is not None

    def test_guild_id_is_primary_key(self, db_session):
        """GuildId should be unique - duplicate insert should fail."""
        prefix1 = GuildPrefix(
            GuildId=123456789,
            Prefix="!",
            CreateDate=datetime.now(UTC),
            Author="User1",
        )
        db_session.add(prefix1)
        db_session.commit()

        # Attempt duplicate
        prefix2 = GuildPrefix(
            GuildId=123456789,
            Prefix="?",
            CreateDate=datetime.now(UTC),
            Author="User2",
        )
        db_session.add(prefix2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()
