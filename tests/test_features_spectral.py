"""Tests for the spectral feature group (H1-H2, HRF).

Parity (the gate): the raw per-interval spectral arrays reproduce the captured
reference arrays, all three fixtures, machine-epsilon. The reference stores its
two outputs *crossed* (V3), and the capture saved them crossed, so parity holds
with the swap reproduced -- the returned ``h1h2`` matches captured ``h1h2`` (which
is actually HRF) and vice versa.

Synthetic definition-check (the flashlight): run on the INTERNAL correctly-named
values (`spectral_params`), a sum of cosines with known harmonic amplitudes must
return hand-computed H1-H2 and HRF. This certifies the *formulas* are right and is
kept deliberately separate from V3's labeling swap -- otherwise the swap would look
like a definition divergence when it is only a relabeling.

Degenerate: `number_partials <= 1` (very high f0) returns a literal 0 for both; no
fixture reaches it (REFERENCE_NOTES.md C5), so a unit test exercises it directly.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.features import (
    extract_voice_features,
    prepare_cycles,
    spectral_params,
    spectral_statistics,
)

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


# --- Parity (the gate), with V3's swap reproduced ---------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_spectral_matches_capture(name):
    """Raw h1h2/hrf reproduce the captured (crossed) reference arrays."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci = d["gci"].astype(np.int64) - 1  # 0-based (GciResult convention)
    h1h2, hrf = spectral_statistics(prepare_cycles(d["feat_u"], d["udash"], gci, fs), fs)

    np.testing.assert_allclose(h1h2, d["feat_h1h2"], rtol=1e-11, atol=1e-13)
    np.testing.assert_allclose(hrf, d["feat_hrf"], rtol=1e-11, atol=1e-13)


def test_capture_is_stored_crossed():
    """Confirm the capture holds the swapped labeling (so parity *needs* the swap).

    If the outputs were stored correctly-named, the un-crossed HRF array would
    match captured ``hrf``. It does not -- it matches captured ``h1h2`` -- proving
    the capture is crossed and the port must cross to match it (V3).
    """
    d = np.load(GOLDEN / "vowel_f0100_16k.npz")
    fs = float(d["input_fs"])
    gci = d["gci"].astype(np.int64) - 1  # 0-based (GciResult convention)
    prep = prepare_cycles(d["feat_u"], d["udash"], gci, fs)
    h1h2_out, hrf_out = spectral_statistics(prep, fs)  # already crossed
    # h1h2_out holds HRF and matches captured "h1h2"; it does NOT match captured "hrf".
    assert np.allclose(h1h2_out, d["feat_h1h2"], rtol=1e-11, atol=1e-13)
    assert not np.allclose(h1h2_out, d["feat_hrf"], rtol=1e-11, atol=1e-13)


# --- Synthetic definition-check on the INTERNAL correctly-named values -------


def test_synthetic_definitions_on_internal_values():
    """`spectral_params` returns the true H1-H2 and HRF for known harmonic amplitudes.

    A sum of cosines at exact FFT bins (so harmonic ``k`` lands on bin ``k``) with
    amplitudes A1..A4 has H1-H2 = 20*log10(A1/A2) and HRF = 10*log10(sum_{k>=2}
    (Ak/A1)^2). fs=16000, period=25 -> f0=640 -> number_partials=4, so bins 1..4
    are exactly the four harmonics. Checked on the correctly-named internals, *not*
    the crossed outputs, so this certifies the formulas independently of V3.
    """
    fs, period = 16000.0, 25  # f0=640 Hz -> floor(3000/640)=4 partials
    amps = [1.0, 0.5, 0.25, 0.1]
    n = np.arange(period)
    useg = sum(a * np.cos(2 * np.pi * (k + 1) * n / period) for k, a in enumerate(amps))

    h1h2, hrf = spectral_params(useg, period, fs, harmonic_limit=3000.0)
    exp_h1h2 = 20 * np.log10(amps[0] / amps[1])
    exp_hrf = 10 * np.log10(sum((amps[k] / amps[0]) ** 2 for k in range(1, 4)))
    np.testing.assert_allclose(h1h2, exp_h1h2, rtol=1e-10)
    np.testing.assert_allclose(hrf, exp_hrf, rtol=1e-10)


def test_synthetic_degenerate_returns_zero():
    """Too few harmonics below the limit -> literal (0, 0), not NaN (REFERENCE_NOTES C5).

    C5 trips on the partial *count* (f0 > 1500 Hz -> floor(3000/f0) <= 1), independent
    of the segment's content or its open phase. It is orthogonal to C4 (the O1==0
    timing/flow zeroing): a short period trips C5 here; a long-period no-open-phase
    cycle trips C4 without tripping C5 (see the C4 decomposition test, where
    number_partials = 37). The two degenerate paths never conflate.
    """
    fs, period = 16000.0, 8  # f0=2000 Hz -> floor(3000/2000)=1 -> degenerate
    useg = np.cos(2 * np.pi * np.arange(period) / period)
    assert spectral_params(useg, period, fs, harmonic_limit=3000.0) == (0.0, 0.0)


# --- Shape: the container is now fully populated ----------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_extract_fills_spectral_fields(name):
    """extract_voice_features now populates h1h2/hrf; no field remains NaN-by-default."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci0 = d["gci"].astype(np.int64) - 1  # 0-based
    vf = extract_voice_features(d["feat_u"], d["udash"], fs, gci0)

    np.testing.assert_allclose(vf.h1h2, d["feat_h1h2"][1:])  # crossed: holds HRF
    np.testing.assert_allclose(vf.hrf, d["feat_hrf"][1:])  # crossed: holds H1-H2
    # No feature group is a NaN placeholder any more.
    for field in ("f0", "mfdr", "cq", "pa", "naq", "h1h2", "hrf", "qoq"):
        assert not np.all(np.isnan(getattr(vf, field))), field
