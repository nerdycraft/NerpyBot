# -*- coding: utf-8 -*-
"""Test Twitch notification and EventSub subscription models."""

from datetime import UTC, datetime

import pytest
from models.twitch import TwitchNotifications, TwitchEventSubSubscription


class TestTwitchNotifications:
    def test_create_and_retrieve(self, db_session):
        row = TwitchNotifications(
            GuildId=111,
            ChannelId=222,
            Streamer="shroud",
            StreamerDisplayName="shroud",
        )
        db_session.add(row)
        db_session.commit()
        found = TwitchNotifications.get_by_id(row.Id, 111, db_session)
        assert found is not None
        assert found.Streamer == "shroud"

    def test_get_all_by_guild(self, db_session):
        db_session.add(TwitchNotifications(GuildId=111, ChannelId=222, Streamer="shroud", StreamerDisplayName="shroud"))
        db_session.add(
            TwitchNotifications(GuildId=111, ChannelId=222, Streamer="pokimane", StreamerDisplayName="pokimane")
        )
        db_session.add(TwitchNotifications(GuildId=999, ChannelId=222, Streamer="xqc", StreamerDisplayName="xqc"))
        db_session.commit()
        results = TwitchNotifications.get_all_by_guild(111, db_session)
        assert len(results) == 2

    def test_get_all_by_streamer(self, db_session):
        db_session.add(TwitchNotifications(GuildId=111, ChannelId=222, Streamer="shroud", StreamerDisplayName="shroud"))
        db_session.add(TwitchNotifications(GuildId=999, ChannelId=333, Streamer="shroud", StreamerDisplayName="shroud"))
        db_session.commit()
        results = TwitchNotifications.get_all_by_streamer("shroud", db_session)
        assert len(results) == 2
        assert all(r.Streamer == "shroud" for r in results)

    def test_get_by_channel_and_streamer(self, db_session):
        db_session.add(TwitchNotifications(GuildId=111, ChannelId=222, Streamer="shroud", StreamerDisplayName="shroud"))
        db_session.commit()
        found = TwitchNotifications.get_by_channel_and_streamer(111, 222, "shroud", db_session)
        assert found is not None
        found_none = TwitchNotifications.get_by_channel_and_streamer(111, 222, "pokimane", db_session)
        assert found_none is None

    def test_unique_constraint(self, db_session):
        from sqlalchemy.exc import IntegrityError

        db_session.add(TwitchNotifications(GuildId=111, ChannelId=222, Streamer="shroud", StreamerDisplayName="shroud"))
        db_session.commit()
        db_session.add(TwitchNotifications(GuildId=111, ChannelId=222, Streamer="shroud", StreamerDisplayName="shroud"))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestTwitchEventSubSubscription:
    def test_create_and_retrieve(self, db_session):
        sub = TwitchEventSubSubscription(
            TwitchSubscriptionId="abc-123",
            StreamerLogin="shroud",
            StreamerUserId="12345",
            EventType="stream.online",
            Status="enabled",
            CreatedAt=datetime.now(UTC),
        )
        db_session.add(sub)
        db_session.commit()
        found = TwitchEventSubSubscription.get_by_streamer_and_type("shroud", "stream.online", db_session)
        assert found is not None
        assert found.TwitchSubscriptionId == "abc-123"

    def test_get_all_enabled(self, db_session):
        db_session.add(
            TwitchEventSubSubscription(
                TwitchSubscriptionId="a",
                StreamerLogin="shroud",
                StreamerUserId="1",
                EventType="stream.online",
                Status="enabled",
                CreatedAt=datetime.now(UTC),
            )
        )
        db_session.add(
            TwitchEventSubSubscription(
                TwitchSubscriptionId="b",
                StreamerLogin="pokimane",
                StreamerUserId="2",
                EventType="stream.online",
                Status="revoked",
                CreatedAt=datetime.now(UTC),
            )
        )
        db_session.commit()
        enabled = TwitchEventSubSubscription.get_all_enabled(db_session)
        assert len(enabled) == 1
        assert enabled[0].StreamerLogin == "shroud"
