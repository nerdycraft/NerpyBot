from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.helpers import error_context, parse_id, send_hidden_message


# --- parse_id ---


def test_parse_id_from_int():
    assert parse_id(283746501234567890) == 283746501234567890


def test_parse_id_from_string():
    assert parse_id("283746501234567890") == 283746501234567890


# --- send_hidden_message ---


@pytest.mark.asyncio
async def test_send_hidden_message_initial_response():
    interaction = MagicMock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()

    await send_hidden_message(interaction, "secret")

    interaction.response.send_message.assert_awaited_once_with("secret", ephemeral=True)


@pytest.mark.asyncio
async def test_send_hidden_message_followup():
    interaction = MagicMock()
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()

    await send_hidden_message(interaction, "followup secret")

    interaction.followup.send.assert_awaited_once_with("followup secret", ephemeral=True)


@pytest.mark.asyncio
async def test_send_hidden_message_passes_kwargs():
    interaction = MagicMock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()

    await send_hidden_message(interaction, "msg", view=MagicMock())

    call_kwargs = interaction.response.send_message.call_args[1]
    assert call_kwargs["ephemeral"] is True
    assert "view" in call_kwargs


# --- error_context ---


def _make_interaction(*, cmd_name="ping", user_name="Alice", user_id=123, guild_name="TestGuild", guild_id=456):
    """Create a mock Interaction (no .interaction attribute)."""
    interaction = MagicMock(spec=["command", "user", "guild"])
    interaction.command.qualified_name = cmd_name
    interaction.user = MagicMock()
    interaction.user.__str__ = lambda self: user_name
    interaction.user.id = user_id
    interaction.guild = MagicMock()
    interaction.guild.name = guild_name
    interaction.guild.id = guild_id
    return interaction


def _make_context(*, cmd_name="sync", author_name="Bob", author_id=789, guild_name="OtherGuild", guild_id=101):
    """Create a mock Context (has .interaction attribute)."""
    ctx = MagicMock()
    ctx.interaction = None  # Context always has .interaction
    ctx.command.qualified_name = cmd_name
    ctx.author = MagicMock()
    ctx.author.__str__ = lambda self: author_name
    ctx.author.id = author_id
    ctx.guild = MagicMock()
    ctx.guild.name = guild_name
    ctx.guild.id = guild_id
    return ctx


def test_error_context_interaction():
    interaction = _make_interaction()
    result = error_context(interaction)
    assert result == "[TestGuild (456)] Alice (123) -> /ping"


def test_error_context_context():
    ctx = _make_context()
    result = error_context(ctx)
    assert result == "[OtherGuild (101)] Bob (789) -> /sync"


def test_error_context_interaction_no_guild():
    interaction = _make_interaction()
    interaction.guild = None
    result = error_context(interaction)
    assert result == "[DM] Alice (123) -> /ping"


def test_error_context_context_no_guild():
    ctx = _make_context()
    ctx.guild = None
    result = error_context(ctx)
    assert result == "[DM] Bob (789) -> /sync"


def test_error_context_no_command():
    interaction = _make_interaction()
    interaction.command = None
    result = error_context(interaction)
    assert result == "[TestGuild (456)] Alice (123) -> /unknown"
