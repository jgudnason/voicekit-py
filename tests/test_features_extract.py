"""Composed golden gate for `extract_voice_features` (the "J4" join).

The per-group tests each validate one feature array against its captured column by
calling one group function directly. This test validates the *composition* -- the
public `extract_voice_features`, driven once, reproducing all ten captured
`feat_*` arrays in a single call. It is the only test that exercises the
orchestration itself: the 0-based -> 1-based gci conversion, the left-edge-drop
slicing, the field assignment (including the V3 h1h2/hrf crossing), and -- once it
lands -- the `O1==0` seam masking. A shared-intermediate divergence or a
field-wiring bug that every per-group test passes will surface here.

It is fed the *captured* `udash`/`feat_u` (not live IAIF output), so it holds on
all three fixtures including 8 kHz, whose live pipeline cannot reproduce the
capture (fixture limitation F1) but whose captured-input features are exact.

This is the behavior-preserving baseline for the shared-prep refactor: it passes
against the current (duplicated per-group) code, and its staying green is the
proof that the refactor changed nothing.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.features import extract_voice_features

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
    np.testing.assert_array_equal(vf.vuv, d["feat_vuv"][1:] == 1.0)
