# -*- coding: utf-8 -*-
"""Tests for account resolution heuristics."""

import json

from utils.blizzard import (
    strip_diacritics,
    name_similarity_score,
    temporal_score,
    account_confidence,
    make_pair_key,
    build_account_groups,
    detect_prefix_families,
    parse_known_mounts,
)


class TestParseKnownMounts:
    def test_legacy_format(self):
        """Legacy list format returns no achievement points."""
        ids, count, ap = parse_known_mounts(json.dumps([1, 2, 3]))
        assert ids == {1, 2, 3}
        assert count == 3
        assert ap is None

    def test_new_format_without_ap(self):
        """New dict format without achievement_points returns None for ap."""
        raw = json.dumps({"ids": [1, 2, 3], "last_count": 5})
        ids, count, ap = parse_known_mounts(raw)
        assert ids == {1, 2, 3}
        assert count == 5
        assert ap is None

    def test_new_format_with_ap(self):
        """New dict format with achievement_points returns all three values."""
        raw = json.dumps({"ids": [1, 2], "last_count": 2, "achievement_points": 15430})
        ids, count, ap = parse_known_mounts(raw)
        assert ids == {1, 2}
        assert count == 2
        assert ap == 15430


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

    def test_long_prefix_substring(self):
        """keetheon / keetheondudu -> 8-char prefix IS the shorter name -> high score."""
        score = name_similarity_score("keetheon", "keetheondudu")
        assert score >= 0.7

    def test_long_prefix_both_long(self):
        """keetheonmage / keetheondudu -> 8-char shared prefix, both 12 chars -> high score."""
        score = name_similarity_score("keetheonmage", "keetheondudu")
        assert score >= 0.7

    def test_long_prefix_nine_chars(self):
        """keetheondh / keetheondudu -> 9-char prefix -> high score."""
        score = name_similarity_score("keetheondh", "keetheondudu")
        assert score >= 0.7

    def test_medium_prefix_six_chars_safe(self):
        """shadow / shadowstep -> 6-char prefix, but short enough to be coincidental."""
        score = name_similarity_score("shadow", "shadowstep")
        assert score < 0.7


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
        """Different names, different mounts, no temporal -> below threshold.

        Mount count similarity fires (both have 200) but as a weak signal
        that alone can't cross the grouping threshold.
        """
        mounts_a = json.dumps(list(range(1, 201)))
        mounts_b = json.dumps(list(range(201, 401)))
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score < 0.7

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

    def test_matching_achievement_points_groups(self):
        """Same achievement points with different names and small mount sets -> high confidence."""
        mounts_a = json.dumps({"ids": list(range(1, 31)), "last_count": 30, "achievement_points": 15430})
        mounts_b = json.dumps({"ids": list(range(1, 31)), "last_count": 30, "achievement_points": 15430})
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score >= 0.7

    def test_achievement_points_within_tolerance(self):
        """AP within ±100 should still count as matching."""
        mounts_a = json.dumps({"ids": [1], "last_count": 1, "achievement_points": 15430})
        mounts_b = json.dumps({"ids": [1], "last_count": 1, "achievement_points": 15500})
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score >= 0.7

    def test_achievement_points_very_different_no_signal(self):
        """AP differing by >100 should not contribute a positive signal."""
        mounts_a = json.dumps({"ids": [1], "last_count": 1, "achievement_points": 15000})
        mounts_b = json.dumps({"ids": [1], "last_count": 1, "achievement_points": 20000})
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score < 0.7

    def test_achievement_points_missing_one_side(self):
        """AP missing on one character should not affect scoring."""
        mounts_a = json.dumps({"ids": list(range(1, 201)), "last_count": 200, "achievement_points": 15430})
        mounts_b = json.dumps({"ids": list(range(1, 201)), "last_count": 200})  # no AP
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        # Should still group via mount Jaccard, AP just doesn't add/subtract
        assert score >= 0.7

    def test_mount_count_similarity_supplements(self):
        """Similar mount counts (same ratio) on small sets act as a supplementary signal."""
        # Both have 30 mounts but different IDs (so no Jaccard match)
        mounts_a = json.dumps({"ids": list(range(1, 31)), "last_count": 30})
        mounts_b = json.dumps({"ids": list(range(31, 61)), "last_count": 30})
        score_with_count = account_confidence(
            name_a="alurush",
            name_b="alublood",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        score_no_mounts = account_confidence(
            name_a="alurush",
            name_b="alublood",
            mounts_a=None,
            mounts_b=None,
            temporal_data=None,
        )
        # Mount count match should provide a boost over name-only
        assert score_with_count > score_no_mounts

    def test_mount_count_very_different_no_signal(self):
        """Very different mount counts should not add a positive signal."""
        mounts_a = json.dumps({"ids": list(range(1, 201)), "last_count": 200})
        mounts_b = json.dumps({"ids": list(range(201, 301)), "last_count": 100})
        score = account_confidence(
            name_a="thrall",
            name_b="jaina",
            mounts_a=mounts_a,
            mounts_b=mounts_b,
            temporal_data=None,
        )
        assert score == 0.0


class TestMakePairKey:
    def test_alphabetical_order(self):
        """Keys should be sorted so (A,B) and (B,A) produce the same key."""
        assert make_pair_key(("alpha", "r1"), ("beta", "r1")) == "alpha:r1|beta:r1"
        assert make_pair_key(("beta", "r1"), ("alpha", "r1")) == "alpha:r1|beta:r1"

    def test_different_realms(self):
        assert make_pair_key(("char", "realm-a"), ("char", "realm-b")) == "char:realm-a|char:realm-b"


class TestBuildAccountGroups:
    def test_diacritics_grouped(self):
        """Characters differing only by diacritics -> same group."""
        candidates = [
            {"name": "morz\u00e2", "realm": "blackhand"},
            {"name": "morza", "realm": "blackhand"},
            {"name": "thrall", "realm": "blackhand"},
        ]
        groups = build_account_groups(candidates, stored_mounts={}, temporal_data={})
        assert groups[("morz\u00e2", "blackhand")] == groups[("morza", "blackhand")]
        assert groups[("thrall", "blackhand")] != groups[("morza", "blackhand")]

    def test_identical_mounts_grouped(self):
        """Characters with identical large mount sets -> same group."""
        mounts = json.dumps(list(range(1, 201)))
        candidates = [
            {"name": "alpha", "realm": "r1"},
            {"name": "beta", "realm": "r1"},
        ]
        stored = {
            ("alpha", "r1"): mounts,
            ("beta", "r1"): mounts,
        }
        groups = build_account_groups(candidates, stored_mounts=stored, temporal_data={})
        assert groups[("alpha", "r1")] == groups[("beta", "r1")]

    def test_all_different(self):
        """Completely unrelated characters -> separate groups."""
        candidates = [
            {"name": "thrall", "realm": "blackhand"},
            {"name": "jaina", "realm": "blackhand"},
            {"name": "sylvanas", "realm": "blackhand"},
        ]
        groups = build_account_groups(candidates, stored_mounts={}, temporal_data={})
        group_ids = set(groups.values())
        assert len(group_ids) == 3

    def test_temporal_only_grouping(self):
        """Weak name + strong temporal -> grouped."""
        candidates = [
            {"name": "alurush", "realm": "r1"},
            {"name": "alublood", "realm": "r1"},
        ]
        pair_key = make_pair_key(("alurush", "r1"), ("alublood", "r1"))
        temporal = {pair_key: {"correlated": 6, "uncorrelated": 0}}
        groups = build_account_groups(candidates, stored_mounts={}, temporal_data=temporal)
        assert groups[("alurush", "r1")] == groups[("alublood", "r1")]

    def test_transitive_grouping(self):
        """If A~B and B~C, then A, B, and C should all be in the same group."""
        candidates = [
            {"name": "morz\u00e2", "realm": "r1"},
            {"name": "morza", "realm": "r1"},
            {"name": "morzb", "realm": "r1"},  # different name, but same mounts as morza
        ]
        mounts = json.dumps(list(range(1, 201)))
        stored = {
            ("morza", "r1"): mounts,
            ("morzb", "r1"): mounts,
        }
        groups = build_account_groups(candidates, stored_mounts=stored, temporal_data={})
        # morza and morza are grouped by name, morza and morzb by mounts -> all 3 grouped
        assert groups[("morz\u00e2", "r1")] == groups[("morza", "r1")]
        assert groups[("morza", "r1")] == groups[("morzb", "r1")]

    def test_long_prefix_all_grouped(self):
        """All keetheon* characters should end up in one group via long prefix."""
        candidates = [
            {"name": "keetheon", "realm": "blackmoore"},
            {"name": "keetheondh", "realm": "blackmoore"},
            {"name": "keetheonmagê", "realm": "blackmoore"},
            {"name": "keetheonshâm", "realm": "blackmoore"},
            {"name": "keetheonspst", "realm": "blackmoore"},
            {"name": "keetheônbdk", "realm": "blackmoore"},
            {"name": "keetheônwl", "realm": "blackmoore"},
            {"name": "keetheondudu", "realm": "blackmoore"},
            {"name": "keetheonhunt", "realm": "blackmoore"},
            {"name": "keetheonlock", "realm": "blackmoore"},
            {"name": "keetheonrmix", "realm": "blackmoore"},
        ]
        groups = build_account_groups(candidates, stored_mounts={}, temporal_data={})
        group_ids = {groups[k] for k in groups}
        assert len(group_ids) == 1, f"Expected 1 group, got {len(group_ids)}: {groups}"

    def test_prefix_family_extends_existing_group(self):
        """alu-like family: 4 chars grouped by mounts, 5th extends via prefix family."""
        mounts = json.dumps(list(range(1, 201)))
        candidates = [
            {"name": "aluclap", "realm": "ravencrest"},
            {"name": "aluh", "realm": "ravencrest"},
            {"name": "alurush", "realm": "ravencrest"},
            {"name": "alusdreieck", "realm": "ravencrest"},
            {"name": "alublood", "realm": "ravencrest"},
        ]
        # 4 of the 5 share identical mounts -> grouped in phase 1
        stored = {
            ("aluclap", "ravencrest"): mounts,
            ("aluh", "ravencrest"): mounts,
            ("alurush", "ravencrest"): mounts,
            ("alusdreieck", "ravencrest"): mounts,
            # alublood has NO mount data
        }
        groups = build_account_groups(candidates, stored_mounts=stored, temporal_data={})
        # alublood should be pulled in by prefix family extension
        group_ids = {groups[k] for k in groups}
        assert len(group_ids) == 1, f"Expected 1 group, got {len(group_ids)}: {groups}"

    def test_prefix_family_minority_not_extended(self):
        """If only a minority of a prefix family is grouped, don't extend."""
        mounts = json.dumps(list(range(1, 201)))
        candidates = [
            {"name": "darkblade", "realm": "r1"},
            {"name": "darkmoon", "realm": "r1"},
            {"name": "darkfire", "realm": "r1"},
            {"name": "darkheart", "realm": "r1"},
            {"name": "darksoul", "realm": "r1"},
        ]
        # Only 2 of 5 share mounts (not majority)
        stored = {
            ("darkblade", "r1"): mounts,
            ("darkmoon", "r1"): mounts,
        }
        groups = build_account_groups(candidates, stored_mounts=stored, temporal_data={})
        # darkblade and darkmoon are grouped, but the other 3 should NOT be pulled in
        assert groups[("darkblade", "r1")] == groups[("darkmoon", "r1")]
        grouped_with_dark = sum(1 for k, g in groups.items() if g == groups[("darkblade", "r1")])
        assert grouped_with_dark == 2, f"Expected only 2 in group, got {grouped_with_dark}"

    def test_prefix_family_no_existing_group(self):
        """Prefix family with no mount/temporal evidence -> no grouping (for short prefixes)."""
        candidates = [
            {"name": "aluclap", "realm": "r1"},
            {"name": "aluh", "realm": "r1"},
            {"name": "alurush", "realm": "r1"},
        ]
        groups = build_account_groups(candidates, stored_mounts={}, temporal_data={})
        # With no mount/temporal data and only 3-char prefix, should not group
        group_ids = set(groups.values())
        assert len(group_ids) == 3

    def test_prefix_family_different_realms_separate(self):
        """Same prefix on different realms should not form a cross-realm family."""
        mounts = json.dumps(list(range(1, 201)))
        candidates = [
            {"name": "alualpha", "realm": "r1"},
            {"name": "alubeta", "realm": "r1"},
            {"name": "alugamma", "realm": "r1"},
            {"name": "aludelta", "realm": "r2"},  # different realm
        ]
        stored = {
            ("alualpha", "r1"): mounts,
            ("alubeta", "r1"): mounts,
            ("alugamma", "r1"): mounts,
        }
        groups = build_account_groups(candidates, stored_mounts=stored, temporal_data={})
        # r1 characters grouped, but r2 character stays separate
        assert groups[("alualpha", "r1")] == groups[("alubeta", "r1")]
        assert groups[("aludelta", "r2")] != groups[("alualpha", "r1")]

    def test_empty_candidates(self):
        """No candidates -> empty groups."""
        groups = build_account_groups([], stored_mounts={}, temporal_data={})
        assert groups == {}


class TestDetectPrefixFamilies:
    def test_basic_family(self):
        """3+ characters sharing a prefix on same realm -> detected as family."""
        candidates = [
            {"name": "aluclap", "realm": "r1"},
            {"name": "aluh", "realm": "r1"},
            {"name": "alurush", "realm": "r1"},
        ]
        families = detect_prefix_families(candidates)
        # All 3 should be in the same family
        assert ("aluclap", "r1") in families
        family = families[("aluclap", "r1")]
        assert ("aluh", "r1") in family
        assert ("alurush", "r1") in family
        assert len(family) == 3

    def test_too_few_members(self):
        """2 characters sharing a prefix -> no family detected."""
        candidates = [
            {"name": "alurush", "realm": "r1"},
            {"name": "alublood", "realm": "r1"},
        ]
        families = detect_prefix_families(candidates)
        assert len(families) == 0

    def test_different_realms(self):
        """Same prefix on different realms -> separate families (or none if < 3)."""
        candidates = [
            {"name": "alualpha", "realm": "r1"},
            {"name": "alubeta", "realm": "r1"},
            {"name": "alugamma", "realm": "r2"},
        ]
        families = detect_prefix_families(candidates)
        # Only 2 on r1, 1 on r2 -> no family meets the threshold
        assert len(families) == 0

    def test_diacritics_normalized(self):
        """Characters with diacritics should be grouped by normalized prefix."""
        candidates = [
            {"name": "keetheon", "realm": "r1"},
            {"name": "keetheonmage", "realm": "r1"},
            {"name": "keetheônwl", "realm": "r1"},
        ]
        families = detect_prefix_families(candidates)
        assert ("keetheon", "r1") in families
        family = families[("keetheon", "r1")]
        assert len(family) == 3
