"""Tests for the per-cycle feature framework (f0, framek, frame_len_ok).

Parity (the gate): the raw per-interval f0/framek/frame_len_ok reproduce the captured
reference arrays, all three fixtures, machine-epsilon. Fed the captured u/gci as
data (u only for its length here).

Synthetic certification (the flashlight, load-bearing for the foundation): a
constant-pitch input certifies the segmentation and voicing test against a known
answer. It also surfaces the reference's period convention -- ``f0 = fs/(period-1)``,
not ``fs/period`` -- which is filed as a feature observation (REFERENCE_NOTES),
reproduced not corrected. Diagnostic, not a gate.

Shape: `extract_voice_features` returns the (d)-aligned container -- one row per
GCI, left-edge non-cycle dropped, framework fields populated and the rest NaN.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.features import cycle_framework, extract_voice_features
from voicekit.features.config import FeaturesConfig

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


# --- Parity (the gate) ------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_framework_matches_capture(name):
    """Raw f0/framek/frame_len_ok reproduce the captured reference arrays."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci = d["gci"].astype(np.int64) - 1  # 0-based (GciResult convention)
    f0, framek, frame_len_ok = cycle_framework(gci, d["feat_u"].size, fs)

    np.testing.assert_allclose(f0, d["feat_f0"], rtol=1e-12, atol=1e-12)
    np.testing.assert_array_equal(framek, d["feat_framek"])
    # Our field is ``frame_len_ok``; the capture key stays ``feat_vuv`` -- it names
    # the MATLAB reference variable (``vuv``), deliberately preserved, not renamed.
    np.testing.assert_array_equal(frame_len_ok, d["feat_vuv"])


# --- Synthetic certification (the flashlight) -------------------------------


def test_synthetic_constant_pitch_certifies_framework():
    """Constant GCI spacing certifies segmentation, voicing, and the period convention.

    With closures every ``P`` samples, each interior cycle spans ``P+1`` inclusive
    samples, so the reference's ``T = len(nn)-2 = P-1`` and ``f0 = fs/(P-1)`` -- a
    known answer that certifies the per-cycle framework. It is deliberately *not*
    ``fs/P`` (the true pitch): the ``-1`` is the reference's period convention,
    reproduced, filed as a feature observation. Here fs=16000, P=160 -> the true
    pitch is 100 Hz but the framework reports fs/159 = 100.63 Hz.
    """
    fs, period = 16000.0, 160
    gci = np.arange(period, 20 * period + 1, period, dtype=np.int64) - 1  # 0-based, evenly spaced
    n_samples = int(gci[-1] + period)
    f0, _framek, frame_len_ok = cycle_framework(gci, n_samples, fs)

    interior = slice(1, -1)  # drop both edge intervals for the clean check
    # Framework computes the reference convention fs/(period-1), exactly.
    np.testing.assert_allclose(f0[interior], fs / (period - 1))
    # ... which is the ~0.63% overestimate of the true pitch, by design (observation).
    assert abs(f0[1] - fs / period) > 0.5  # not fs/period
    assert abs(f0[1] - fs / (period - 1)) < 1e-9  # is fs/(period-1)
    # Frame length: interior cycles (100 Hz) have a period in (40, 400) Hz -> flagged.
    assert np.all(frame_len_ok[interior] == 1.0)


def test_synthetic_voicing_bounds():
    """A period outside the voiced F0 range is flagged unvoiced."""
    fs = 16000.0
    # Period ~1000 samples -> 16 Hz, below voicing_f0_min=40 -> unvoiced.
    gci = np.arange(1000, 5001, 1000, dtype=np.int64) - 1  # 0-based
    f0, _framek, frame_len_ok = cycle_framework(gci, int(gci[-1] + 1000), fs)
    assert np.all(frame_len_ok[1:-1] == 0.0)  # interior cycles out of range (too low)


# --- Shape ------------------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_extract_shape_is_gci_aligned(name):
    """extract_voice_features returns one (d)-aligned row per GCI, framework fields filled."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci0 = d["gci"].astype(np.int64) - 1  # 0-based, GciResult convention
    vf = extract_voice_features(d["feat_u"], d["udash"], fs, gci0)

    n = gci0.size
    for field in ("f0", "framek", "frame_len_ok", "mfdr", "cq", "pa", "naq", "h1h2", "hrf", "qoq"):
        assert getattr(vf, field).shape == (n,), field
    # Populated framework fields equal the captured raw arrays with the left edge
    # dropped; framek converted to 0-based.
    np.testing.assert_allclose(vf.f0, d["feat_f0"][1:])
    np.testing.assert_array_equal(vf.framek, d["feat_framek"][1:].astype(np.int64) - 1)
    np.testing.assert_array_equal(vf.frame_len_ok, d["feat_vuv"][1:] == 1.0)  # capture key kept
    # Framework fields are populated (the rest are covered by their own groups).
    assert not np.all(np.isnan(vf.f0))


def test_config_declares_all_knobs():
    """FeaturesConfig fixes the whole config shape now, even fields this build ignores."""
    cfg = FeaturesConfig()
    for knob in (
        "voicing_f0_min", "voicing_f0_max", "open_threshold", "quasi_open_level",
        "medfilt_window", "harmonic_limit_hz",
    ):
        assert hasattr(cfg, knob), knob
    # The glottal-flow integration cutoff (the reference's misnamed f_preemph) is NOT
    # a FeaturesConfig knob: it belongs to derive_flow, which runs before extraction.
    assert not hasattr(cfg, "preemph")
