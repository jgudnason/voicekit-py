"""Tests for phase-slope projection.

Two checks, kept separate:

1. Golden master (sole arbiter) -- projected candidates against the MATLAB
   capture on all three fixtures, exact integer equality after the
   1-based/0-based bridge. The captured gdwav is fed as data (piece-2 output
   as fixture, not via group_delay.py): this stage is tested in isolation.
2. Orthogonal, hand-built features (fixture- and library-independent) -- a
   synthetic gdwav with a single turning-point feature at known indices, with
   the min-to-max gap chosen 5 (== 1 mod 4) and a half-integer midpoint value
   so a wrong (half-to-even) rounding disagrees. The expected projected index
   is hand-computed with MATLAB round semantics, pinning both the projection
   geometry and the rounding convention. There is no clean library
   cross-check for this DYPSA-specific projection, so none is used.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga import phase_slope as ps

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


# --- 1. Golden master (the arbiter) ----------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_projection_matches_capture(name):
    """Projected candidates reproduce MATLAB psp exactly (1-based/0-based bridge)."""
    d = np.load(GOLDEN / f"{name}.npz")
    candidates = ps.phase_slope_projection(d["gdwav"])
    ref = d["pro_cand"]
    assert candidates.shape == ref.shape
    # MATLAB indices are 1-based, ours 0-based; integer locations, so exact.
    np.testing.assert_array_equal(candidates + 1, ref)


# --- 2. Orthogonal, hand-built features ------------------------------------


def test_negative_maximum_projection_and_rounding():
    """A lone sub-zero maximum projects to a hand-computed index (MATLAB round).

    Extrema are put on single-sample plateaus so gdot is exactly zero at the
    extremum (found without snap ambiguity) and gdotdot is cleanly nonzero
    there. Min at index 10, sub-zero max at 15, gap 5 so the midpoint arg is
    2.5 -- half-away-from-zero rounds to 3, half-to-even to 2. The rising
    segment is set so the MATLAB midpoint m = 13 has g[13] = -12.5, another
    half-integer where the two roundings disagree:
        m = 10 + round(2.5) = 13;  nz = 13 - round(-12.5) = 13 - (-13) = 26
    Half-to-even would give 28 (wrong midpoint) or 25 (wrong value), so this
    pins the rounding convention as well as the geometry.
    """
    g = np.zeros(40)
    g[0:11] = np.linspace(-8.0, -21.5, 11)  # descend to the min at 10
    g[11] = -21.5  # min plateau (10, 11)
    g[12], g[13], g[14], g[15] = -17.0, -12.5, -9.5, -6.5  # rise, g[13] = -12.5
    g[16] = -6.5  # max plateau (15, 16), value < 0
    g[17:40] = np.linspace(-8.0, -20.0, 23)  # descend after the max

    candidates = ps.phase_slope_projection(g)
    np.testing.assert_array_equal(candidates, [26.0])


def test_positive_minimum_projection_branch():
    """A lone above-zero minimum projects from the min->following-max midpoint.

    Mirror of the negative-maximum case for the other branch, same plateau
    construction. Turning points at 20 (max), 25 (min > 0), 30 (max); the
    positive minimum at 25 projects from the midpoint to the following max at
    30 (gap 5, m = 28). g[28] = 6.5 is a half-integer where the roundings
    disagree: nz = 28 - round(6.5) = 28 - 7 = 21 (half-to-even would give 22).
    """
    g = np.zeros(45)
    g[0:21] = np.linspace(2.0, 10.1, 21)  # rise to the max at 20
    g[21] = 10.1  # max plateau (20, 21)
    g[22], g[23], g[24], g[25] = 8.0, 6.0, 4.5, 3.1  # descend to the min at 25
    g[26] = 3.1  # min plateau (25, 26), value > 0
    g[27], g[28], g[29], g[30] = 5.0, 6.5, 8.0, 10.1  # rise, g[28] = 6.5
    g[31] = 10.1  # max plateau (30, 31)
    g[32:45] = np.linspace(8.0, 1.0, 13)  # descend after

    candidates = ps.phase_slope_projection(g)
    np.testing.assert_array_equal(candidates, [21.0])
