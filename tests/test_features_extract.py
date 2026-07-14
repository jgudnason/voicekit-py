"""Composed golden gate for `extract_voice_features` (the "J4" join).

The per-group tests each validate one feature array against its captured column by
calling one group function directly. This test validates the *composition* -- the
public `extract_voice_features`, driven once, reproducing all ten captured
`feat_*` arrays in a single call. It is the only test that exercises the
orchestration itself: the 0-based -> 1-based gci conversion, the left-edge-drop
slicing, the field assignment (including the V3 h1h2/hrf crossing), and the `O1==0`
seam masking. A shared-intermediate divergence or a field-wiring bug that every
per-group test passes will surface here.

It is fed the *captured* `udash`/`feat_u` (not live IAIF output), so it holds on
all three fixtures including 8 kHz, whose live pipeline cannot reproduce the
capture (fixture limitation F1) but whose captured-input features are exact.

It is the behavior-preserving anchor for the shared-prep hoist: it reproduces the
capture whether the per-cycle prep is duplicated across the groups or computed once
in `prepare_cycles`, so it staying green through that refactor proved it changed no
values (the five flow/timing features stayed bitwise-0).
"""

import warnings
from pathlib import Path

import numpy as np
import pytest

from voicekit.features import (
    apply_cycle_mask,
    extract_voice_features,
    flow_statistics,
    prepare_cycles,
    spectral_statistics,
    timing_statistics,
)


def _rosenberg(period: int) -> np.ndarray:
    """A Rosenberg-like flow pulse (open 40%, return 16%) -- a clean voiced cycle."""
    t1, t2 = int(0.4 * period), int(0.16 * period)
    x = np.zeros(period)
    x[:t1] = 0.5 * (1 - np.cos(np.pi * np.arange(t1) / t1))
    x[t1 : t1 + t2] = np.cos(np.pi * np.arange(t2) / (2 * t2))
    return x

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]

# f0, h1h2, hrf cannot be bitwise-equal to the capture even on identical inputs:
# f0 is fs/T here vs the reference's 1/(T/fs) (one IEEE rounding apart), and h1h2/hrf
# carry FFT/log reassociation vs MATLAB. That epsilon is inherent, not introduced.
# Observed rel <= 6.7e-16; the bound below is tight, far under any reassociation the
# commit-6 hoist could add. The other seven are asserted exact (see below).
_RTOL, _ATOL = 1e-12, 1e-13


@pytest.mark.filterwarnings("error")  # a stray RuntimeWarning from reordered prep must fail here
@pytest.mark.parametrize("name", FIXTURES)
def test_extract_matches_capture_all_ten(name):
    """All ten features from one composed call reproduce the captured arrays.

    The five flow/timing features are asserted **exactly** (`array_equal`): on
    identical captured inputs with identical operations they are bitwise-0 versus
    the capture on all three fixtures (measured). Commit 6 hoists useg/uuseg and the
    DC-shift -- the arrays these five are computed from -- into shared prep; if that
    reassociates the arithmetic, 0.0 becomes ~1e-16 and only an exact assertion
    catches it. A tolerance here would wave through the one refactor this test
    guards. If commit 6 turns any of the five red, find the reassociation; do not
    relax the assertion.
    """
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    # Public convention is 0-based (GciResult); the capture is 1-based. Feeding
    # captured_gci - 1 exercises the exact conversion the live orchestrator uses.
    gci0 = d["gci"].astype(np.int64) - 1
    vf = extract_voice_features(d["feat_u"], d["udash"], fs, gci0)

    # The reference arrays are len(gci)+1; extract drops the left-edge non-cycle,
    # so each vf field aligns to feat_*[1:].
    # Five flow/timing features: exact (bitwise-0 baseline, the refactor guard).
    np.testing.assert_array_equal(vf.mfdr, d["feat_mfdr"][1:])
    np.testing.assert_array_equal(vf.pa, d["feat_pa"][1:])
    np.testing.assert_array_equal(vf.naq, d["feat_naq"][1:])
    np.testing.assert_array_equal(vf.cq, d["feat_cq"][1:])
    np.testing.assert_array_equal(vf.qoq, d["feat_qoq"][1:])
    # f0/h1h2/hrf: tight rtol (inherent FFT/log and fs/T-vs-1/(T/fs) epsilon).
    # h1h2/hrf are stored crossed on both sides (observation V3): vf.h1h2 holds the
    # reference's HRF, and the capture's feat_h1h2 does too, so they match directly.
    np.testing.assert_allclose(vf.f0, d["feat_f0"][1:], rtol=_RTOL, atol=_ATOL)
    np.testing.assert_allclose(vf.h1h2, d["feat_h1h2"][1:], rtol=_RTOL, atol=_ATOL)
    np.testing.assert_allclose(vf.hrf, d["feat_hrf"][1:], rtol=_RTOL, atol=_ATOL)

    # framek is emitted 0-based (VoiceFeatures convention); the capture is 1-based.
    # The +1 here mirrors the 0-based gci input convention -- one rule at both ends of
    # the public boundary. It is not a cancelling pair with the input +1: the two act
    # on different quantities (gci inbound, framek outbound) and are each independently
    # load-bearing (framek is genuinely 1-based before its output -1).
    np.testing.assert_array_equal(vf.framek + 1, d["feat_framek"][1:].astype(np.int64))
    np.testing.assert_array_equal(vf.frame_len_ok, d["feat_vuv"][1:] == 1.0)  # capture key kept


def test_apply_cycle_mask_assigns_only_the_subset_where_masked():
    """The reusable (mask, subset, value) step: assigns value to subset cells under the
    mask, leaves everything else untouched, and selects rather than multiplies.

    In the pipeline the O1==0 mask is redundant (the groups already leave 0), so this
    unit test is where the mechanism itself is exercised. mask = [T, F, T]:
      - a masked cell -> value, whatever it held (incl. nan): the nan->0 rescue;
      - an UNMASKED nan survives untouched -- the select semantics (0*nan would poison it);
      - an array outside the subset is not touched at all.
    """
    raw = {
        "cq": np.array([1.0, 2.0, np.nan]),  # masked cells 0 and 2 (2 holds nan)
        "mfdr": np.array([5.0, np.nan, 6.0]),  # unmasked cell 1 holds nan
        "hrf": np.array([7.0, 8.0, 9.0]),  # not in the subset -> must be untouched
    }
    mask = np.array([True, False, True])
    apply_cycle_mask(raw, mask, ("cq", "mfdr"), 0.0)

    np.testing.assert_array_equal(raw["cq"], [0.0, 2.0, 0.0])  # masked value and masked nan -> 0
    np.testing.assert_array_equal(raw["mfdr"], [0.0, np.nan, 0.0])  # unmasked nan survives (select)
    np.testing.assert_array_equal(raw["hrf"], [7.0, 8.0, 9.0])  # outside subset -> unchanged


def test_c4_o1_zero_cycle_decomposition():
    """C4: a no-open-phase cycle zeroes the five timing/flow features -- by self-zero
    AND by mask, proving the mask redundant (the distinction commit 6 preserves).

    The cycle is a long-period constant-0 plateau with a narrow negative notch: it
    reaches O1==0 by plateau-collapse (the DC-shift drives max ~ 0, so the 5% mask is
    all-False), yet stays spectrally non-degenerate (number_partials = 37, so C5's
    literal-0 guard is NOT tripped -- C4 and C5 are orthogonal here; see
    REFERENCE_NOTES C5). No committed fixture reaches O1==0 (C4).

    Three assertions:
      (1) the groups, called directly, return 0.0 on the notch cycle -- from their
          0.0 init (the reference value), with no mask involved. If the pre-mask
          group output were anything but 0.0 this must fail; that is the invariant.
      (2) composed extract_voice_features also returns 0.0 there -- mask applied.
      (1)+(2) together: the seam mask is a redundant safety net, not the sole rescue.
    Flanking cycles carry genuinely nonzero five, so "neighbors unmasked" is not
    vacuous. And the whole path raises no warning.
    """
    fs, p = 16000.0, 201  # T = 199 -> f0 ~ 80 Hz -> number_partials 37 (C5 not tripped)
    normal = _rosenberg(p) * 1000.0
    notch = np.zeros(p)
    notch[p // 2 : p // 2 + 3] = -500.0  # narrow notch at 50%, outside the [10%,30%] window
    u = np.concatenate([normal, normal, notch, normal, normal, normal[:50]])
    uu = np.concatenate([[0.0], np.diff(u)]) * fs
    gci = np.array([p, 2 * p, 3 * p, 4 * p], dtype=np.int64) - 1  # 0-based; notch is raw cycle 2
    notch_ig = 2

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # the whole C4 path must be warning-free
        preps = prepare_cycles(u, uu, gci, fs)
        assert preps[notch_ig].o1 == 0  # no open phase, by plateau-collapse

        # (1) groups self-zero the O1==0 cycle from init -- the reference value, no mask.
        mfdr, pa, naq = flow_statistics(preps, fs)
        cq, qoq = timing_statistics(preps)
        assert (mfdr[notch_ig], pa[notch_ig], naq[notch_ig], cq[notch_ig], qoq[notch_ig]) == (
            0.0, 0.0, 0.0, 0.0, 0.0,
        )
        # spectral is not masked and not degenerate here (C5 orthogonal) -> finite.
        h1h2, hrf = spectral_statistics(preps, fs)
        assert np.isfinite(h1h2[notch_ig]) and np.isfinite(hrf[notch_ig])
        # neighbors carry genuinely nonzero five (masking not vacuous).
        for ig in (1, 3):
            assert all(v != 0.0 for v in (mfdr[ig], pa[ig], naq[ig], cq[ig], qoq[ig]))

        # (2) composed extract also yields 0 on that cycle -- the seam mask applied.
        vf = extract_voice_features(u, uu, fs, gci)

    i = notch_ig - 1  # vf drops the left-edge non-cycle
    assert (vf.mfdr[i], vf.pa[i], vf.naq[i], vf.cq[i], vf.qoq[i]) == (0.0, 0.0, 0.0, 0.0, 0.0)
    assert vf.f0[i] != 0.0  # f0 is NOT masked (reference still sets 1/Ttime)
    assert np.isfinite(vf.h1h2[i]) and np.isfinite(vf.hrf[i])  # spectral not masked
    for i_n in (0, 2):  # composed neighbors of the notch cycle
        vals = (vf.mfdr[i_n], vf.pa[i_n], vf.naq[i_n], vf.cq[i_n], vf.qoq[i_n])
        assert all(v != 0.0 for v in vals)
