# -*- coding: utf-8 -*-
"""Tests for utils/format.py - Discord text formatting utilities"""

from utils.format import bold, box, inline, italics, pagify, strikethrough, underline


class TestBox:
    """Tests for box() Discord code block formatting."""

    def test_box_without_language(self):
        """Box without language should use triple backticks."""
        result = box("code here")
        assert result == "```\ncode here\n```"

    def test_box_with_language(self):
        """Box with language should include language specifier."""
        result = box("print('hello')", "python")
        assert result == "```python\nprint('hello')\n```"

    def test_box_with_multiline_content(self):
        """Multi-line content should be preserved."""
        content = "line 1\nline 2\nline 3"
        result = box(content, "md")
        assert result == "```md\nline 1\nline 2\nline 3\n```"

    def test_box_empty_string(self):
        """Empty content should still produce valid box."""
        result = box("")
        assert result == "```\n\n```"


class TestInline:
    """Tests for inline() Discord inline code formatting."""

    def test_inline_basic(self):
        """Text should be wrapped in single backticks."""
        assert inline("code") == "`code`"

    def test_inline_with_spaces(self):
        """Spaces should be preserved."""
        assert inline("some code") == "`some code`"

    def test_inline_empty_string(self):
        """Empty string should produce empty inline."""
        assert inline("") == "``"


class TestTextFormatting:
    """Tests for bold(), italics(), strikethrough(), underline()."""

    def test_bold(self):
        """Text should be wrapped in double asterisks."""
        assert bold("text") == "**text**"

    def test_italics(self):
        """Text should be wrapped in single asterisks."""
        assert italics("text") == "*text*"

    def test_strikethrough(self):
        """Text should be wrapped in double tildes."""
        assert strikethrough("text") == "~~text~~"

    def test_underline(self):
        """Text should be wrapped in double underscores."""
        assert underline("text") == "__text__"

    def test_formatting_empty_strings(self):
        """Empty strings should produce valid formatting markers."""
        assert bold("") == "****"
        assert italics("") == "**"
        assert strikethrough("") == "~~~~"
        assert underline("") == "____"

    def test_formatting_with_special_chars(self):
        """Special characters should be preserved."""
        assert bold("hello!@#$%") == "**hello!@#$%**"


class TestPagify:
    """Tests for pagify() text pagination for Discord's 2000 char limit."""

    def test_short_text_single_page(self):
        """Short text should return single page."""
        text = "Short text"
        pages = list(pagify(text))
        assert len(pages) == 1
        assert pages[0] == "Short text"

    def test_long_text_splits_on_newline(self):
        """Long text should split on newline delimiter."""
        # Create text that exceeds page_length
        line = "A" * 100
        text = "\n".join([line] * 25)  # 2500 chars + newlines

        pages = list(pagify(text, page_length=500))
        assert len(pages) > 1
        # Each page should be under the limit
        for page in pages:
            assert len(page) <= 500

    def test_respects_custom_delimiters(self):
        """Custom delimiters should be used for splitting."""
        text = "Word1 Word2 Word3 Word4 Word5"
        pages = list(pagify(text, delims=[" "], page_length=12))
        # Should split at space delimiter
        assert len(pages) > 1
        # Verify we're splitting at spaces
        for page in pages[:-1]:  # All but last page
            assert len(page) <= 12

    def test_delimiter_at_position_zero_doesnt_hang(self):
        """Delimiter at position 0 should not cause infinite loop.

        When rfind returns 0 (delimiter at start of remaining text),
        the function should fall back to page_length to make progress.
        """
        # Delimiter "---" will end up at position 0 after first split
        text = "Part1---Part2---Part3"
        pages = list(pagify(text, delims=["---"], page_length=10))
        # Should complete without hanging
        assert len(pages) > 1
        # All content should be present
        combined = "".join(pages)
        assert "Part1" in combined
        assert "Part2" in combined
        assert "Part3" in combined

    def test_splits_at_page_length_without_delimiter(self):
        """If no delimiter found, should split at page_length."""
        text = "A" * 100  # 100 chars, no delimiters
        pages = list(pagify(text, delims=["\n"], page_length=30))
        # Should have multiple pages
        assert len(pages) > 1
        # First pages should be exactly page_length
        assert len(pages[0]) == 30

    def test_empty_string(self):
        """Empty string should return single empty page."""
        pages = list(pagify(""))
        assert len(pages) == 1
        assert pages[0] == ""

    def test_exact_page_length_text(self):
        """Text exactly at page_length should be single page."""
        text = "A" * 2000
        pages = list(pagify(text, page_length=2000))
        assert len(pages) == 1

    def test_default_page_length_is_2000(self):
        """Default page_length should be 2000 (Discord limit)."""
        text = "A" * 2001
        pages = list(pagify(text))
        # Should split since it exceeds default 2000
        assert len(pages) == 2

    def test_multiple_delimiters(self):
        """Multiple delimiters should find closest to page boundary."""
        # Space delimiter closer to boundary than newline
        text = "Hello World\nLong text here"
        pages = list(pagify(text, delims=["\n", " "], page_length=15))
        assert len(pages) > 1
