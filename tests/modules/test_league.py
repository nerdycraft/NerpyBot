# -*- coding: utf-8 -*-
"""Tests for modules.league — localized summoner embed fields."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models.admin import GuildLanguageConfig
from modules.league import League
from utils.strings import load_strings


@pytest.fixture(autouse=True)
def _load_locale_strings():
    load_strings()


@pytest.fixture
def cog(mock_bot):
    mock_bot.config = {"league": {"riot": "fake-riot-key"}}
    cog = League.__new__(League)
    cog.bot = mock_bot
    cog.config = mock_bot.config["league"]
    cog.version = "14.1.1"
    return cog


@pytest.fixture
def interaction(mock_interaction):
    mock_interaction.guild.id = 987654321
    mock_interaction.guild_id = 987654321
    return mock_interaction


def _mock_riot_api(summoner_data, rank_data):
    """Create a nested mock that simulates aiohttp ClientSession context managers."""

    def make_response(data):
        resp = AsyncMock()
        resp.json = AsyncMock(return_value=data)
        return resp

    summoner_resp = make_response(summoner_data)
    rank_resp = make_response(rank_data)

    call_count = 0

    def session_factory(*args, **kwargs):
        nonlocal call_count
        session = AsyncMock()

        if call_count == 0:
            # First ClientSession — summoner lookup
            session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=summoner_resp)))
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)
        else:
            # Second ClientSession — rank lookup
            session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=rank_resp)))
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=False)

        call_count += 1
        return session

    return session_factory


SUMMONER_DATA = {
    "id": "abc123",
    "name": "TestPlayer",
    "summonerLevel": 42,
    "profileIconId": 1234,
}

RANK_DATA = [
    {
        "rank": "I",
        "tier": "GOLD",
        "leaguePoints": 75,
        "wins": 100,
        "losses": 50,
    }
]


# ---------------------------------------------------------------------------
# /league summoner — English
# ---------------------------------------------------------------------------


class TestSummonerEnglish:
    async def test_summoner_embed_fields(self, cog, interaction):
        with patch("modules.league.ClientSession", side_effect=_mock_riot_api(SUMMONER_DATA, RANK_DATA)):
            await League.summoner.callback(cog, interaction, "EUW1", "TestPlayer")

        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Summoner Level: 42" in emb.description
        field_names = [f.name for f in emb.fields]
        assert "Rank" in field_names
        assert "League Points" in field_names
        assert "Wins" in field_names
        assert "Losses" in field_names

    async def test_summoner_no_ranked(self, cog, interaction):
        with patch("modules.league.ClientSession", side_effect=_mock_riot_api(SUMMONER_DATA, [])):
            await League.summoner.callback(cog, interaction, "EUW1", "TestPlayer")

        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Summoner Level: 42" in emb.description
        assert len(emb.fields) == 0


# ---------------------------------------------------------------------------
# /league summoner — German
# ---------------------------------------------------------------------------


class TestSummonerGerman:
    async def test_summoner_embed_fields_german(self, cog, interaction, db_session):
        db_session.add(GuildLanguageConfig(GuildId=987654321, Language="de"))
        db_session.commit()

        with patch("modules.league.ClientSession", side_effect=_mock_riot_api(SUMMONER_DATA, RANK_DATA)):
            await League.summoner.callback(cog, interaction, "EUW1", "TestPlayer")

        emb = interaction.response.send_message.call_args[1]["embed"]
        assert "Beschwörerstufe: 42" in emb.description
        field_names = [f.name for f in emb.fields]
        assert "Rang" in field_names
        assert "Ligapunkte" in field_names
        assert "Siege" in field_names
        assert "Niederlagen" in field_names
