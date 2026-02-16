# -*- coding: utf-8 -*-
"""Tests for account resolution heuristics."""

import json

from utils.account_resolution import strip_diacritics, name_similarity_score, temporal_score, account_confidence


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


class TestTemporalScore:
    def test_no_events(self):
        assert temporal_score(0, 0) == 0.0

    def test_one_correlated(self):
        """Single correlated event — weak signal."""
        score = temporal_score(1, 0)
        assert 0.1 <= score <= 0.3

    def test_strong_correlation(self):
        """5+ correlated, 0 uncorrelated — very strong."""
        score = temporal_score(5, 0)
        assert score >= 0.7

    def test_mixed_signals(self):
        """5 correlated, 3 uncorrelated — moderate."""
        score = temporal_score(5, 3)
        assert 0.3 <= score <= 0.7

    def test_mostly_uncorrelated(self):
        """2 correlated, 8 uncorrelated — weak."""
        score = temporal_score(2, 8)
        assert score < 0.2

    def test_cap_at_0_8(self):
        """Even with massive correlation, caps at 0.8."""
        score = temporal_score(100, 0)
        assert score <= 0.8


class TestAccountConfidence:
    def test_identical_mount_sets(self):
        """Two characters with same 200+ mounts -> high confidence."""
        mounts_a = json.dumps(list(range(1, 201)))
        mounts_b = json.dumps(list(range(1, 201)))
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score >= 0.7

    def test_similar_names_no_mounts(self):
        """Diacritics match alone -> high confidence."""
        score = account_confidence(
            name_a="morz\u00e2",
            name_b="morza",
            mounts_a=None,
            mounts_b=None,
            temporal_data=None,
        )
        assert score >= 0.7

    def test_different_everything(self):
        """Different names, different mounts, no temporal -> 0.0."""
        mounts_a = json.dumps(list(range(1, 201)))
        mounts_b = json.dumps(list(range(201, 401)))
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score == 0.0

    def test_multiple_signals_boost(self):
        """Name match + mount identity -> boosted above either alone."""
        mounts = json.dumps(list(range(1, 201)))
        score_combined = account_confidence(
            name_a="morz\u00e2",
            name_b="morza",
            mounts_a=mounts,
            mounts_b=mounts,
            temporal_data=None,
        )
        score_name_only = account_confidence(
            name_a="morz\u00e2",
            name_b="morza",
            mounts_a=None,
            mounts_b=None,
            temporal_data=None,
        )
        assert score_combined > score_name_only

    def test_prefix_name_plus_temporal(self):
        """Weak name signal + temporal correlation -> crosses threshold over time."""
        score = account_confidence(
            name_a="alurush",
            name_b="alublood",
            mounts_a=None,
            mounts_b=None,
            temporal_data={"correlated": 5, "uncorrelated": 0},
        )
        assert score >= 0.7

    def test_small_mount_set_ignored(self):
        """Identical mount sets under 50 mounts should not count as strong signal."""
        mounts = json.dumps(list(range(1, 11)))  # only 10 mounts
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts,
            mounts_b=mounts,
            temporal_data=None,
        )
        assert score < 0.7

    def test_all_signals_caps_at_1(self):
        """Even with all signals maxed, confidence should not exceed 1.0."""
        mounts = json.dumps(list(range(1, 201)))
        score = account_confidence(
            name_a="morza",
            name_b="morza",
            mounts_a=mounts,
            mounts_b=mounts,
            temporal_data={"correlated": 100, "uncorrelated": 0},
        )
        assert score <= 1.0

    def test_temporal_only(self):
        """Strong temporal signal with completely different names and no mounts."""
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=None,
            mounts_b=None,
            temporal_data={"correlated": 10, "uncorrelated": 0},
        )
        assert score >= 0.7
