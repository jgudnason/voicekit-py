"""Tests for GOI detection (step 5b).

Two things are tested separately: the *raw* GOI sequence (the reference's `goi`,
sentinels and all) for golden parity, and the raw->clean per-cycle derivation
that produces the public `GciResult.goi`.

The raw path is validated stage-isolated on captured inputs: the leftover
candidates go through the reused `forward_pass`/`traceback` with the causal
closed-phase cost, then the `postGOI` pairing (REFERENCE_NOTES entry 5). It must
reproduce the captured `goi` exactly -- including the `-1` sentinels and the glide
count mismatch.

The raw->clean derivation has no captured arbiter of its own (clean is derived
from raw), so it gets its own orthogonal test with a hand-built raw array, plus a
specific assertion for the glide after-last opening.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga.detector import YagaConfig, _align_goi_to_cycles, _detect_goi_raw

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


@pytest.mark.parametrize("name", FIXTURES)
def test_raw_goi_matches_capture(name):
    """The raw GOI sequence (with postGOI pairing) reproduces captured goi exactly."""
    d = np.load(GOLDEN / f"{name}.npz")
    raw = _detect_goi_raw(
        d["dp_gcic"][:, 0].astype(np.int64),
        d["dp_gcic"][:, 1].astype(np.int64),
        d["dp_sew"],
        d["cencost"],
        d["gci_dp"].astype(np.int64),
        d["gci"].astype(np.int64),
        d["udash"],
        d["fnwav"],
        float(d["input_fs"]),
        YagaConfig(),
    )
    np.testing.assert_array_equal(np.sort(raw), np.sort(d["goi"].astype(np.float64)))


def test_align_derivation_places_openings_and_drops_sentinels():
    """raw->clean: sentinel drops, in-cycle opening assigned, after-last opening kept.

    GCIs at 100/200/300/400 (1-based). A raw array with a -1 sentinel (below the
    first GCI -> dropped), an opening at 150 (in cycle 100-200 -> slot 0), and an
    opening at 450 (after the last GCI -> slot 3); cycles 200-300 and 300-400 have
    none (NaN). Returned 0-based.
    """
    gci = np.array([100, 200, 300, 400], dtype=np.int64)
    raw = np.array([-1.0, 150.0, 450.0])
    goi = _align_goi_to_cycles(gci, raw)

    assert goi.shape == gci.shape
    np.testing.assert_array_equal(goi[0], 149.0)  # 150 (1-based) -> 149 (0-based), cycle 0
    assert np.isnan(goi[1]) and np.isnan(goi[2])  # empty cycles
    np.testing.assert_array_equal(goi[3], 449.0)  # after-last opening, final slot


def test_glide_after_last_opening_lands_in_final_slot():
    """glide's extra opening (after the last GCI) is placed in the last cycle, not dropped."""
    d = np.load(GOLDEN / "vowel_glide_16k.npz")
    gci = np.sort(d["gci"].astype(np.int64))
    raw = d["goi"].astype(np.float64)
    goi = _align_goi_to_cycles(gci, raw)

    after_last = np.sort(raw[raw > gci[-1]])
    assert after_last.size == 1  # glide has exactly one opening past the last closure
    np.testing.assert_array_equal(goi[-1], after_last[0] - 1)  # in the final slot, 0-based
