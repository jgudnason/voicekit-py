"""GIF5 frame->cycle mapping: which cycles a rank-deficient frame invalidates.

The per-frame validity flag is turned into a per-cycle mask by span overlap. This
is the load-bearing seam (a wrong mapping silently NaNs the wrong cycles), so the
synthetic test asserts the exact cycle indices, not just "some cycle went NaN".
"""

import numpy as np

from voicekit.gif.weighted_lp import WeightedLpResult, invalid_cycle_mask


def _result(frame_starts, frame_valid, n_samples) -> WeightedLpResult:
    # only uu.size, frame_starts, frame_valid matter to the mapping
    return WeightedLpResult(
        u=np.zeros(n_samples),
        uu=np.zeros(n_samples),
        weight=np.ones(n_samples),
        frame_starts=np.asarray(frame_starts, dtype=np.int64),
        frame_valid=np.asarray(frame_valid, dtype=np.bool_),
    )


def test_only_cycles_overlapping_the_invalid_frame_are_masked() -> None:
    # Frames start at 0/100/200/300 over 400 samples; frame 2 ([200, 300)) is
    # invalid. GCIs at 50/150/250/350 -> cycles [50,150) [150,250) [250,350)
    # [350,400). Both cycle 1 ([150,250), overlapping 200..249) and cycle 2
    # ([250,350), overlapping 250..299) touch [200,300) and are masked; the fully
    # outside cycles 0 and 3 are not. Any touching cycle is masked (conservative).
    r = _result([0, 100, 200, 300], [True, True, False, True], 400)
    gci = np.array([50, 150, 250, 350], dtype=np.int64)
    mask = invalid_cycle_mask(gci, r)
    assert mask.tolist() == [False, True, True, False]


def test_cycle_straddling_the_invalid_frame_boundary_is_masked() -> None:
    # A cycle straddling the start of the invalid frame draws corrupted flow ->
    # masked (overlap, not GCI-membership). Frame 2 ([200,300)) invalid; a cycle
    # [180, 260) straddles 200, so it is masked even though its GCI (180) is in the
    # valid frame 1.
    r = _result([0, 100, 200, 300], [True, True, False, True], 400)
    gci = np.array([180, 260], dtype=np.int64)  # cycles [180,260) and [260,400)
    mask = invalid_cycle_mask(gci, r)
    assert mask.tolist() == [True, True]  # both overlap [200,300)


def test_all_valid_masks_nothing() -> None:
    r = _result([0, 100, 200], [True, True, True], 300)
    gci = np.array([50, 150, 250], dtype=np.int64)
    assert not invalid_cycle_mask(gci, r).any()


def test_last_cycle_extends_to_signal_end() -> None:
    # The last cycle spans [gci[-1], n_samples). Frame 1 ([100, 300)) is invalid,
    # covering most of the signal: cycle 0 [50,300) overlaps 100..299 and the last
    # cycle [250,300) overlaps too, so both are masked.
    r = _result([0, 100], [True, False], 300)
    gci = np.array([50, 250], dtype=np.int64)
    mask = invalid_cycle_mask(gci, r)
    assert mask.tolist() == [True, True]
