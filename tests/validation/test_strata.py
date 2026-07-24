"""OpenGlot R1 stratification: the primary/whispery split and its enforcement."""

from __future__ import annotations

import pytest
from validation.openglot.strata import (
    BREAKDOWN_AXES,
    PRIMARY,
    STRATA,
    WHISPERY,
    pooled_stratum,
    stratum_of,
)
from validation.report import Standing


def test_primary_is_the_modal_trio_pooled() -> None:
    assert set(PRIMARY.members) == {"normal", "breathy", "creaky"}
    assert PRIMARY.standing is Standing.PRIMARY


def test_whispery_is_a_separate_stratum_with_primary_standing() -> None:
    # Separate stratum (weak excitation) but same reference authority (analytic t_e):
    # stratum separation and standing are orthogonal.
    assert WHISPERY.members == ("whispery",)
    assert WHISPERY.standing is Standing.PRIMARY
    assert WHISPERY.name != PRIMARY.name


def test_strata_are_disjoint_and_cover_the_four_modes() -> None:
    members = [m for s in STRATA for m in s.members]
    assert sorted(members) == ["breathy", "creaky", "normal", "whispery"]
    assert len(members) == len(set(members))  # disjoint


def test_vowel_and_f0_are_breakdowns_not_strata() -> None:
    assert set(BREAKDOWN_AXES) == {"vowel", "f0"}


def test_pooling_within_a_stratum_is_allowed() -> None:
    assert pooled_stratum(("normal", "breathy", "creaky")) is PRIMARY
    assert pooled_stratum(("whispery",)) is WHISPERY


def test_pooling_a_primary_mode_with_whispery_raises() -> None:
    with pytest.raises(ValueError, match="cannot pool across strata"):
        pooled_stratum(("normal", "whispery"))


def test_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="unknown phonation mode"):
        stratum_of("shouty")
