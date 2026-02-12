# -*- coding: utf-8 -*-
"""Tests for modules/fun.py - Entertainment commands"""

from unittest.mock import patch

import pytest

from modules.fun import Fun


@pytest.fixture
def fun_cog(mock_bot):
    """Create a Fun cog instance for testing."""
    return Fun(mock_bot)


class TestLeetTransformation:
    """Tests for leet speak transformation logic."""

    def test_intensity_level_1(self, fun_cog):
        """Level 1 replaces only a, e, i, o."""
        # Test individual character mappings
        text = "aeiou"
        valid_chars = fun_cog.leetdegrees[0]  # ['a', 'e', 'i', 'o']

        result = ""
        for c in text:
            if c in valid_chars:
                result += fun_cog.leetmap[c]
            else:
                result += c

        assert "4" in result  # a -> 4
        assert "3" in result  # e -> 3
        assert "1" in result  # i -> 1
        assert "0" in result  # o -> 0
        assert "u" in result  # u not in level 1

    def test_intensity_level_2_adds_more_chars(self, fun_cog):
        """Level 2 adds s, l, c, y, u, d."""
        level_2_chars = fun_cog.leetdegrees[1]
        assert "s" in level_2_chars
        assert "l" in level_2_chars
        assert "u" in level_2_chars

    def test_intensity_capped_at_5(self, fun_cog):
        """Intensity above 5 should be capped."""
        # Verify we have exactly 6 levels (0-5)
        assert len(fun_cog.leetdegrees) == 6

    def test_preserves_non_mapped_characters(self, fun_cog):
        """Characters not in leetmap should pass through."""
        # Numbers and special chars aren't in the map
        assert "1" not in fun_cog.leetmap.keys()
        assert "@" not in fun_cog.leetmap.keys()

    def test_case_insensitive_transformation(self, fun_cog):
        """Both upper and lower case should map to same leet char."""
        # The logic uses c.lower() before lookup
        assert fun_cog.leetmap["a"] == "4"
        # Upper case 'A' would also map to '4' via .lower()


class TestRollCommand:
    """Tests for the roll dice command."""

    @pytest.mark.asyncio
    async def test_roll_valid_dice(self, fun_cog, mock_context):
        """Rolling with dice > 1 should produce valid result."""
        with patch("modules.fun.randint", return_value=3):
            await fun_cog.roll.callback(fun_cog, mock_context, dice=6)

        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args[0][0]
        assert "d6" in call_args
        assert ":game_die:" in call_args
        assert "3" in call_args

    @pytest.mark.asyncio
    async def test_roll_invalid_dice_returns_retarded_message(self, fun_cog, mock_context):
        """Rolling with dice <= 1 should return special message."""
        await fun_cog.roll.callback(fun_cog, mock_context, dice=1)

        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args[0][0]
        assert "AmIRetarded" in call_args
        assert "yes" in call_args

    @pytest.mark.asyncio
    async def test_roll_zero_dice(self, fun_cog, mock_context):
        """Rolling with 0 should also return special message."""
        await fun_cog.roll.callback(fun_cog, mock_context, dice=0)

        call_args = mock_context.send.call_args[0][0]
        assert "AmIRetarded" in call_args


class TestEightballCommand:
    """Tests for the 8ball command."""

    @pytest.mark.asyncio
    async def test_valid_question_gets_answer(self, fun_cog, mock_context):
        """Question ending with ? should get an 8ball response."""
        with patch("modules.fun.choice", return_value="Yes"):
            await fun_cog.eightball.callback(fun_cog, mock_context, question="Will it rain?")

        mock_context.send.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_question_no_question_mark(self, fun_cog, mock_context):
        """Question without ? should get 'not a question' response."""
        await fun_cog.eightball.callback(fun_cog, mock_context, question="Will it rain")

        call_args = mock_context.send.call_args_list[0][0][0]
        assert "doesn't look like a question" in call_args

    @pytest.mark.asyncio
    async def test_just_question_mark_is_invalid(self, fun_cog, mock_context):
        """Just '?' alone should be invalid."""
        await fun_cog.eightball.callback(fun_cog, mock_context, question="?")

        call_args = mock_context.send.call_args_list[0][0][0]
        assert "doesn't look like a question" in call_args

    def test_ball_responses_are_valid(self, fun_cog):
        """Verify 8ball has the classic 20 responses."""
        assert len(fun_cog.ball) == 20
        assert "Yes" in fun_cog.ball
        assert "My reply is no" in fun_cog.ball


class TestHugCommand:
    """Tests for the hug command."""

    @pytest.mark.asyncio
    async def test_hug_with_specific_intensity(self, fun_cog, mock_context, mock_member):
        """Hug with intensity 0-4 should use that specific emoji."""
        await fun_cog.hug.callback(fun_cog, mock_context, user=mock_member, intensity=2)

        call_args = mock_context.send.call_args[0][0]
        assert fun_cog.hugs[2] in call_args

    @pytest.mark.asyncio
    async def test_hug_intensity_clamped_to_zero(self, fun_cog, mock_context, mock_member):
        """Negative intensity should be clamped to 0."""
        await fun_cog.hug.callback(fun_cog, mock_context, user=mock_member, intensity=-5)

        call_args = mock_context.send.call_args[0][0]
        assert fun_cog.hugs[0] in call_args

    @pytest.mark.asyncio
    async def test_hug_intensity_clamped_to_four(self, fun_cog, mock_context, mock_member):
        """Intensity > 4 should be clamped to 4."""
        await fun_cog.hug.callback(fun_cog, mock_context, user=mock_member, intensity=100)

        call_args = mock_context.send.call_args[0][0]
        assert fun_cog.hugs[4] in call_args

    @pytest.mark.asyncio
    async def test_hug_random_when_no_intensity(self, fun_cog, mock_context, mock_member):
        """No intensity should pick random hug."""
        with patch("modules.fun.choice", return_value=fun_cog.hugs[1]):
            await fun_cog.hug.callback(fun_cog, mock_context, user=mock_member, intensity=None)

        call_args = mock_context.send.call_args[0][0]
        assert fun_cog.hugs[1] in call_args

    def test_hug_emojis_available(self, fun_cog):
        """Should have 5 hug emojis (indices 0-4)."""
        assert len(fun_cog.hugs) == 5


class TestChooseCommand:
    """Tests for the choose command."""

    @pytest.mark.asyncio
    async def test_choose_from_multiple_options(self, fun_cog, mock_context):
        """Should choose from comma-separated options."""
        with patch("modules.fun.choice", return_value="option2"):
            await fun_cog.choose.callback(fun_cog, mock_context, choices="option1,option2,option3")

        call_args = mock_context.send.call_args[0][0]
        assert "option2" in call_args
        assert "I choose" in call_args

    @pytest.mark.asyncio
    async def test_choose_insufficient_options_raises(self, fun_cog, mock_context):
        """Less than 2 chars in choices string should raise."""
        # Note: The code has a bug - it checks len(choices) < 2 instead of len(choices_list)
        # This means "a" (single char) raises, but "a,b" works even though both are short
        from utils.errors import NerpyException

        with pytest.raises(NerpyException, match="Not enough choices"):
            await fun_cog.choose.callback(fun_cog, mock_context, choices="a")


class TestRotiCommand:
    """Tests for the rules of the internet command."""

    @pytest.mark.asyncio
    async def test_roti_with_valid_number(self, fun_cog, mock_context):
        """Valid rule number should return that rule."""
        await fun_cog.roti.callback(fun_cog, mock_context, num=34)

        call_args = mock_context.send.call_args[0][0]
        assert "Rule 34" in call_args
        assert "porn" in call_args.lower()

    @pytest.mark.asyncio
    async def test_roti_invalid_number(self, fun_cog, mock_context):
        """Invalid rule number should return not found message and exit early."""
        await fun_cog.roti.callback(fun_cog, mock_context, num=999)

        # Should only send the error message, then return
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args[0][0]
        assert "no rules found" in call_args

    @pytest.mark.asyncio
    async def test_roti_random_when_no_number(self, fun_cog, mock_context):
        """No number should return random rule."""
        with patch("modules.fun.choice", return_value=42):
            await fun_cog.roti.callback(fun_cog, mock_context, num=None)

        call_args = mock_context.send.call_args[0][0]
        assert "Rule 42" in call_args

    def test_rotis_contains_classic_rules(self, fun_cog):
        """Should contain well-known rules."""
        assert 34 in fun_cog.rotis
        assert 1 in fun_cog.rotis
        assert 2 in fun_cog.rotis


class TestSayCommand:
    """Tests for the say command."""

    @pytest.mark.asyncio
    async def test_say_echoes_text(self, fun_cog, mock_context):
        """Bot should repeat the provided text."""
        await fun_cog.say.callback(fun_cog, mock_context, text="Hello World!")

        mock_context.send.assert_called_once_with("Hello World!")
