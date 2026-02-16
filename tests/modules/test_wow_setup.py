# -*- coding: utf-8 -*-
"""Tests for guild news setup duplicate detection."""

import pytest
from sqlalchemy.exc import IntegrityError

from models.wow import WowGuildNewsConfig


class TestUniqueGuildConfig:
    """Verify unique constraint on (GuildId, WowGuildName, WowRealmSlug, Region)."""

    def _make_config(self, **overrides):
        defaults = {
            "GuildId": 123456,
            "ChannelId": 789,
            "WowGuildName": "test-guild",
            "WowRealmSlug": "blackrock",
            "Region": "eu",
            "Language": "en",
            "Enabled": True,
        }
        defaults.update(overrides)
        return WowGuildNewsConfig(**defaults)

    def test_duplicate_raises_integrity_error(self, db_session):
        """Inserting same guild+realm+region for same Discord guild should fail."""
        db_session.add(self._make_config())
        db_session.flush()

        db_session.add(self._make_config(ChannelId=999))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_different_realm_is_allowed(self, db_session):
        """Different realm slug should not conflict."""
        db_session.add(self._make_config())
        db_session.add(self._make_config(WowRealmSlug="azshara"))
        db_session.flush()

    def test_different_discord_guild_is_allowed(self, db_session):
        """Different Discord guild should not conflict."""
        db_session.add(self._make_config())
        db_session.add(self._make_config(GuildId=999999))
        db_session.flush()

    def test_different_region_is_allowed(self, db_session):
        """Same guild on different region should not conflict."""
        db_session.add(self._make_config())
        db_session.add(self._make_config(Region="us"))
        db_session.flush()


class TestGetExisting:
    """Verify the get_existing classmethod for duplicate lookup."""

    def test_finds_existing(self, db_session):
        config = WowGuildNewsConfig(
            GuildId=123456,
            ChannelId=789,
            WowGuildName="test-guild",
            WowRealmSlug="blackrock",
            Region="eu",
            Language="en",
            Enabled=True,
        )
        db_session.add(config)
        db_session.flush()

        result = WowGuildNewsConfig.get_existing(123456, "test-guild", "blackrock", "eu", db_session)
        assert result is not None
        assert result.Id == config.Id

    def test_returns_none_when_no_match(self, db_session):
        result = WowGuildNewsConfig.get_existing(123456, "test-guild", "blackrock", "eu", db_session)
        assert result is None
