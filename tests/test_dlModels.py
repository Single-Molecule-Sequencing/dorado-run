# tests/test_dlModels.py
"""Tests for dlModels — mods_flag decoding and model candidate selection."""

import pytest

from dorado_run.dlModels import decode_mods_flag, _candidates_for_mod, _latest_of


# ── decode_mods_flag ─────────────────────────────────────────────────────────


class TestDecodModsFlag:

    def test_zero_returns_empty(self):
        assert decode_mods_flag(0) == []

    @pytest.mark.parametrize("flag,expected", [
        (1, ["5mCG_5hmCG"]),
        (2, ["5mC_5hmC"]),
        (3, ["4mC_5mC"]),
        (4, ["5mC"]),
    ])
    def test_cytosine_only(self, flag, expected):
        assert decode_mods_flag(flag) == expected

    def test_adenine_only(self):
        assert decode_mods_flag(8) == ["6mA"]

    @pytest.mark.parametrize("flag,expected", [
        (9,  ["5mCG_5hmCG", "6mA"]),
        (10, ["5mC_5hmC", "6mA"]),
        (11, ["4mC_5mC", "6mA"]),
        (12, ["5mC", "6mA"]),
    ])
    def test_combined(self, flag, expected):
        assert decode_mods_flag(flag) == expected

    def test_invalid_cytosine_bits_exits(self):
        with pytest.raises(SystemExit, match="not valid"):
            decode_mods_flag(5)  # cyto bits = 5, out of range


# ── _candidates_for_mod ─────────────────────────────────────────────────────


_SAMPLE_MODELS = [
    "dna_r10.4.1_e8.2_400bps_sup@v5.0.0_5mCG_5hmCG@v2.0.1",
    "dna_r10.4.1_e8.2_400bps_sup@v5.0.0_5mCG_5hmCG@v3.0.0",
    "dna_r10.4.1_e8.2_400bps_hac@v5.0.0_5mCG_5hmCG@v3.0.0",
    "dna_r10.4.1_e8.2_400bps_sup@v5.0.0_6mA@v1.0.0",
    "dna_r10.4.1_e8.2_400bps_hac@v5.0.0_6mA@v3.0.0",
    "dna_r10.4.1_e8.2_400bps_sup@v4.3.0_5mCG_5hmCG@v2.0.1",
    "dna_r10.4.1_e8.2_400bps_sup@v5.0.0_polish_bacterial_methylation@v1.0",
    "rna_model@v1.0.0_5mCG_5hmCG@v1.0.0",  # not dna
]


class TestCandidatesForMod:

    def test_filters_by_mod_type(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "5.0.0", "5mCG_5hmCG")
        assert len(result) == 3
        assert all("5mCG_5hmCG" in r for r in result)

    def test_filters_by_simplex_version(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "4.3.0", "5mCG_5hmCG")
        assert len(result) == 1
        assert "v4.3.0" in result[0]

    def test_excludes_polish_bacterial(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "5.0.0", "polish_bacterial_methylation")
        # Explicitly excluded
        assert result == []

    def test_excludes_non_dna(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "", "5mCG_5hmCG")
        assert all(r.startswith("dna") for r in result)

    def test_filters_by_tier_sup(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "5.0.0", "5mCG_5hmCG",
                                     simplex_tier="sup")
        assert len(result) == 2
        assert all("_sup@v" in r for r in result)

    def test_filters_by_tier_hac(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "5.0.0", "5mCG_5hmCG",
                                     simplex_tier="hac")
        assert len(result) == 1
        assert "_hac@v" in result[0]

    def test_tier_empty_matches_all(self):
        """When simplex_tier is empty, no tier filtering is applied."""
        result = _candidates_for_mod(_SAMPLE_MODELS, "5.0.0", "6mA")
        assert len(result) == 2  # both sup and hac

    def test_tier_and_version_combined(self):
        result = _candidates_for_mod(_SAMPLE_MODELS, "5.0.0", "6mA",
                                     simplex_tier="sup")
        assert len(result) == 1
        assert "_sup@v5.0.0_6mA@v" in result[0]


# ── _latest_of ───────────────────────────────────────────────────────────────


class TestLatestOf:

    def test_picks_highest_version(self):
        names = [
            "model@v5.0.0_mod@v1.0.0",
            "model@v5.0.0_mod@v2.0.1",
            "model@v5.0.0_mod@v1.5.0",
        ]
        assert _latest_of(names) == "model@v5.0.0_mod@v2.0.1"

    def test_empty_returns_none(self):
        assert _latest_of([]) is None

    def test_single_element(self):
        assert _latest_of(["only_one@v1.0.0"]) == "only_one@v1.0.0"
