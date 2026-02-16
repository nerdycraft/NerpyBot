# -*- coding: utf-8 -*-
"""Tests for account resolution heuristics."""

from utils.account_resolution import strip_diacritics, name_similarity_score


class TestStripDiacritics:
    def test_plain_ascii(self):
        assert strip_diacritics("morza") == "morza"

    def test_circumflex(self):
        assert strip_diacritics("morza\u0302") == "morza"  # combining circumflex

    def test_precomposed(self):
        """Precomposed a-circumflex should decompose and strip."""
        assert strip_diacritics("morz\u00e2") == "morza"

    def test_mixed_case(self):
        assert strip_diacritics("MorzA") == "morza"

    def test_empty(self):
        assert strip_diacritics("") == ""


class TestNameSimilarityScore:
    def test_identical_after_diacritics(self):
        """Morza with and without accent -> 0.9."""
        score = name_similarity_score("morz\u00e2", "morza")
        assert score == 0.9

    def test_shared_prefix_alu(self):
        """alurush / alublood -> shared prefix 'alu' (3 chars)."""
        score = name_similarity_score("alurush", "alublood")
        assert 0.3 <= score <= 0.6

    def test_shared_prefix_alu_wush(self):
        """alurush / aluwush -> shared prefix 'alu' + high similarity."""
        score = name_similarity_score("alurush", "aluwush")
        assert 0.3 <= score <= 0.7

    def test_completely_different(self):
        """thrall / jaina -> 0.0."""
        score = name_similarity_score("thrall", "jaina")
        assert score == 0.0

    def test_same_name(self):
        """Exact same name -> 0.9."""
        score = name_similarity_score("arthas", "arthas")
        assert score == 0.9

    def test_short_prefix_ignored(self):
        """'al' prefix (2 chars) should not trigger prefix matching."""
        score = name_similarity_score("alpha", "albedo")
        # 2-char prefix 'al' is below threshold
        assert score < 0.5
