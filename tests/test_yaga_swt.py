"""Tests for the YAGA stationary wavelet transform and multiscale product.

Three orthogonal checks, kept deliberately separate (see DESIGN.md and the
capture README):

1. Coefficient identity — our bior1.5 taps are the right filter, cross-checked
   against PyWavelets (up to the known sign/order transform). This validates
   the *taps*, not the transform.
2. Golden master — swd/swa match the MATLAB capture at tight tolerance. This
   is the arbiter of the transform, including the deliberate one-sample
   boundary offset that departs from stock SWT. We do NOT compare against
   ``pywt.swt`` here: pywt implements the textbook alignment we depart from,
   so it would disagree at the edges by construction.
3. Delta response — the impulse response pins the upsampling phase and the
   boundary offset independently of both pywt and the fixture.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga import swt

GOLDEN = Path(__file__).resolve().parent / "golden"
# The 8 kHz fixture drives the reference SWT with a clean ground-truth residual
# (its IAIF residual is NaN-prone at 8 kHz; see the capture README), so its
# swd/swa/mp are valid golden masters. Between them the three fixtures cover
# no-pad (%8==0), and both pad remainders (glide pad 3, 8k pad 7).
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


@pytest.fixture(scope="module")
def wfilters():
    """Canonical bior1.5 decomposition filters as MATLAB wfilters returns them."""
    return np.load(GOLDEN / "wfilters_bior15.npz")


# --- 1. Coefficient identity ------------------------------------------------


def test_taps_match_committed_wfilters(wfilters):
    """swt.py's runtime taps equal the committed capture (single source, no drift)."""
    np.testing.assert_allclose(swt.BIOR15_LO_D, wfilters["Lo_D"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(swt.BIOR15_HI_D, wfilters["Hi_D"], rtol=0, atol=1e-12)


def test_wfilters_are_bior15_via_pywt(wfilters):
    """Cross-check the captured taps are genuinely bior1.5, per PyWavelets.

    The transform is the same filter up to convention: MATLAB's lowpass equals
    pywt's dec_lo (and is symmetric); MATLAB's highpass is pywt's dec_hi
    reversed and negated. This confirms the filter identity only — it says
    nothing about the transform alignment, which the fixture pins.
    """
    pywt = pytest.importorskip("pywt")
    w = pywt.Wavelet("bior1.5")
    dec_lo = np.asarray(w.dec_lo)
    dec_hi = np.asarray(w.dec_hi)
    np.testing.assert_allclose(wfilters["Lo_D"], dec_lo, atol=1e-12)
    np.testing.assert_allclose(wfilters["Hi_D"], -dec_hi[::-1], atol=1e-12)


# --- 2. Golden master (the arbiter) ----------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_swt_matches_matlab_capture(name):
    """swd/swa reproduce the MATLAB swtalign output at tight tolerance."""
    d = np.load(GOLDEN / f"{name}.npz")
    result = swt.stationary_wavelet_transform(d["udash"], levels=int(d["nlev"]))

    assert result.detail.shape == d["swd"].shape
    assert result.approx.shape == d["swa"].shape
    np.testing.assert_allclose(result.detail, d["swd"], rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(result.approx, d["swa"], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_multiscale_product_matches_capture(name):
    """The multiscale product reproduces the reference ``mp = prod(swd)``."""
    d = np.load(GOLDEN / f"{name}.npz")
    mp = swt.multiscale_product(d["udash"], levels=int(d["nlev"]))
    np.testing.assert_allclose(mp, d["mp"], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_negative_cube_root_matches_capture(name):
    """The GCI-branch cube root of the negative half reproduces the captured crnmp."""
    d = np.load(GOLDEN / f"{name}.npz")
    np.testing.assert_allclose(swt.negative_cube_root(d["mp"]), d["crnmp"], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", ["vowel_glide_16k", "vowel_f0120_8k"])
def test_pad_and_trim_path_exercised(name):
    """The pad/trim path: a non-multiple-of-8 length round-trips to itself."""
    d = np.load(GOLDEN / f"{name}.npz")
    n = int(d["nu"])
    assert n % 8 != 0, f"{name} was supposed to exercise padding"
    # Output is trimmed back to the (non-multiple-of-8) input length.
    result = swt.stationary_wavelet_transform(d["udash"], levels=3)
    assert result.detail.shape[1] == n


# --- 3. Delta response (independent alignment pin) -------------------------


def _atrous_taps_at_level(taps: np.ndarray, level: int, n: int) -> np.ndarray:
    """Independently build the level's upsampled filter, zero-padded to length n."""
    stride = 1 << (level - 1)
    up = np.zeros(n)
    for i, c in enumerate(taps):
        up[(i * stride) % n] += c
    return up


def test_delta_response_is_atrous_filter_level1():
    """Level-1 impulse response equals the à-trous filter at the SWT offset.

    Feeding a unit impulse, level-1 detail[n] = hi[(n + lf//2 - 1) mod s] and
    approx[n] = lo[(n + lf//2 - 1) mod s]. This pins both the upsampling phase
    and the one-sample boundary offset without reference to pywt or the
    fixture: it is a direct statement about where each tap lands.
    """
    s = 64
    x = np.zeros(s)
    x[0] = 1.0
    result = swt.stationary_wavelet_transform(x, levels=3)

    lf = swt.BIOR15_LO_D.shape[0]  # level 1: stride 1, lf = 10
    shift = lf // 2 - 1
    idx = (np.arange(s) + shift) % s
    lo_pad = _atrous_taps_at_level(swt.BIOR15_LO_D, 1, s)
    hi_pad = _atrous_taps_at_level(swt.BIOR15_HI_D, 1, s)
    np.testing.assert_allclose(result.approx[0], lo_pad[idx], atol=1e-12)
    np.testing.assert_allclose(result.detail[0], hi_pad[idx], atol=1e-12)


def test_delta_detail_localizes_the_offset():
    """The level-1 detail impulse response has its ±1/√2 pair at samples 0,1.

    A concrete, hand-checkable consequence of the offset: with the short
    highpass (nonzero only at taps 4,5) and offset lf//2-1 = 4, the impulse
    response is nonzero exactly at n=0 (-1/√2) and n=1 (+1/√2). Stock SWT's
    lf+1 offset would place them one sample earlier (wrapping n=0 to the tail).
    """
    s = 64
    x = np.zeros(s)
    x[0] = 1.0
    detail1 = swt.stationary_wavelet_transform(x, levels=1).detail[0]
    expected = np.zeros(s)
    expected[0] = -0.707106781186548
    expected[1] = 0.707106781186548
    np.testing.assert_allclose(detail1, expected, atol=1e-12)
