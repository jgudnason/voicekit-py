"""Closed-phase 0/1 weight (GIF2): synthetic decomposition of the mask.

Asserts *which samples are zeroed by which rule* on constructed GCI/GOI
sequences with known closed-phase spans -- the mask decomposition, not just a
final flow. The construction is also validated bit-exactly against the reference
``weightsForLP`` cp-case via MATLAB in the capture path; these are the CI-safe
pins. With ``fs = 2000`` and the default config: ``maxSamplesPerCycle =
ceil(2000/50) = 40`` and ``cpDelay = round(0.9e-3 * 2000) = round(1.8) = 2``.
"""

import numpy as np

from voicekit.gif import ClosedPhaseConfig, closed_phase_weight

FS = 2000.0
CFG = ClosedPhaseConfig()
CP_DELAY = 2  # round(0.9e-3 * 2000)
MAX_SPC = 40  # ceil(2000 / 50)


def _zeroed(w: np.ndarray) -> set[int]:
    return set(np.flatnonzero(w == 0.0).tolist())


def test_mask_is_binary() -> None:
    gci = np.array([30, 70], dtype=np.int64)
    goi = np.array([50, 90], dtype=np.int64)
    w = closed_phase_weight(gci, goi, 100, FS, CFG)
    assert set(np.unique(w).tolist()) <= {0.0, 1.0}
    assert w.shape == (100,)


def test_within_spurt_return_and_open_phase_zeroed() -> None:
    # No boundary dummies: gci[0]=30 <= 40, gci[-1]=70 >= 100-40. One interval
    # 30->70 (gap 40, not > 40) -> within-spurt.
    gci = np.array([30, 70], dtype=np.int64)
    goi = np.array([50, 999], dtype=np.int64)  # goi[1] unused (last GCI, no interval)
    w = closed_phase_weight(gci, goi, 100, FS, CFG)
    # return phase [gci, gci+cpDelay] inclusive = {30, 31, 32}; open phase
    # [goi, next_gci] inclusive = {50..70}. Closed phase {33..49} stays 1.
    expected = set(range(30, 33)) | set(range(50, 71))
    assert _zeroed(w) == expected
    assert np.all(w[33:50] == 1.0)  # the closed phase is preserved


def test_between_spurt_suppresses_only_ahead_of_gci_and_skips_open_phase() -> None:
    # gap 30->90 = 60 > 40 -> between voiced spurts. Only a cpDelay region ahead
    # of the GCI is zeroed; the open-phase line is skipped (continue).
    gci = np.array([30, 90], dtype=np.int64)
    goi = np.array([50, 999], dtype=np.int64)
    w = closed_phase_weight(gci, goi, 100, FS, CFG)
    # [max(0, gci-cpDelay), gci] inclusive of the GCI = {28, 29, 30}.
    assert _zeroed(w) == {28, 29, 30}
    # the open-phase span [50, 90] is NOT zeroed (goi never indexed on this branch)
    assert np.all(w[50:91] == 1.0)


def test_between_spurt_zeroing_is_inclusive_of_the_gci_sample() -> None:
    # The reference line w(max(1,gci-cpDelay):gci)=0 is inclusive of the GCI, so
    # the GCI sample itself (0-based 30) is zeroed -- the +1 a 0-based rendering
    # drops. Sample 31 (just past the GCI) stays 1.
    gci = np.array([30, 90], dtype=np.int64)
    goi = np.array([50, 999], dtype=np.int64)
    w = closed_phase_weight(gci, goi, 100, FS, CFG)
    assert w[30] == 0.0  # the GCI sample is suppressed (inclusive end)
    assert w[31] == 1.0


def test_boundary_dummy_prepend_and_append() -> None:
    # gci[0]=50 > 40 -> a dummy GCI at 0 is prepended; gci[-1]=150 < 300-40=260
    # -> a dummy GCI at n-1 appended. Every cycle here exceeds maxSamplesPerCycle,
    # so all take the between-spurt branch: each suppresses only a cpDelay region
    # ahead of the LEFT GCI of the pair (gci(in)), and the NaN dummy openings are
    # never indexed (no crash). The pairs are (dummy@0, 50), (50, 150), (150,
    # dummy@n-1); the last dummy is never a left GCI, so nothing is zeroed near it.
    gci = np.array([50, 150], dtype=np.int64)
    goi = np.array([80, 180], dtype=np.int64)
    n = 300
    w = closed_phase_weight(gci, goi, n, FS, CFG)
    assert set(np.unique(w).tolist()) <= {0.0, 1.0}  # no NaN leaked in
    # ahead of dummy@0: w(max(1,0-2):0] -> {0}; ahead of 50: {48,49,50};
    # ahead of 150: {148,149,150}. Nothing near the trailing dummy@299.
    assert _zeroed(w) == {0, 48, 49, 50, 148, 149, 150}
    # the open phases (80, 180) are never zeroed -- all cycles are between-spurt
    assert w[80] == 1.0 and w[180] == 1.0
