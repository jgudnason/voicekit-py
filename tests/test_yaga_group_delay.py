"""Tests for the energy-weighted group delay and its GCI candidates.

Two checks, kept separate (as with the SWT):

1. Golden master (the arbiter) — the group-delay function, candidates, slopes
   and toff against the MATLAB capture at tight tolerance, on all three
   fixtures. The input is the captured ``crnmp`` (piece 1's output as data,
   not via swt.py): this stage is tested in isolation.
2. Impulse response (fixture- and library-independent) — a single energy
   spike makes the centroid reduce to the bare ramp, so there is exactly one
   negative-going crossing, landing at the spike. This pins the ramp sign,
   the window centring and the toff alignment without the fixture or any
   library. There is no clean library cross-check for this DYPSA-specific
   group delay, so none is used.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga import group_delay as gd

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


# --- 1. Golden master (the arbiter) ----------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_group_delay_matches_capture(name):
    """gdwav, its raw centroid, candidates, slopes and toff reproduce MATLAB."""
    d = np.load(GOLDEN / f"{name}.npz")
    u = d["crnmp"]  # the reference feeds r = crnmp into xewgrdel
    fs = float(d["input_fs"])
    result = gd.energy_weighted_group_delay(u, fs)

    # Aligned, sign-flipped group delay (the arbiter for the function).
    np.testing.assert_allclose(result.group_delay, d["gdwav"], rtol=1e-10, atol=1e-10)
    # Raw centroid before the sign flip / shift.
    np.testing.assert_allclose(result.centroid, d["gdwav_raw"], rtol=1e-10, atol=1e-10)
    # toff scalar, exact integer.
    assert result.toff == int(d["toff"])
    # Candidates: MATLAB's zero-crossing indices are 1-based, ours 0-based.
    assert result.candidates.shape == d["zcr_cand_raw"].shape
    np.testing.assert_allclose(
        result.candidates + 1, d["zcr_cand_raw"], rtol=1e-9, atol=1e-9
    )
    # Slopes (differences of adjacent centroid samples) are frame-independent.
    np.testing.assert_allclose(result.slopes, d["sew_raw"], rtol=1e-9, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_group_delay_length_pins_window(name):
    """Structural: len(gdwav) == len(u) - (gw - 1), pinning gw / the startup drop."""
    d = np.load(GOLDEN / f"{name}.npz")
    u = d["crnmp"]
    fs = float(d["input_fs"])
    gw = gd.odd_window_length(gd.GroupDelayConfig().gw_len, fs)
    result = gd.energy_weighted_group_delay(u, fs)
    assert result.group_delay.shape[0] == len(u) - (gw - 1)


# --- 2. Impulse response (independent alignment pin) -----------------------


def test_impulse_gives_single_crossing_at_spike():
    """A lone energy spike yields exactly one negative-going crossing, at the spike.

    With u a single impulse at p, the denominator (local energy) and numerator
    (ramp-weighted energy) are both the window shifted to p, so their ratio is
    the bare descending ramp: one negative-going zero crossing, at p after the
    toff alignment.
    """
    fs = 16000.0
    n = 4000
    p = 2000
    u = np.zeros(n)
    u[p] = 1.0
    result = gd.energy_weighted_group_delay(u, fs)

    assert result.candidates.shape == (1,)
    np.testing.assert_allclose(result.candidates[0], p, atol=1e-9)
    assert result.slopes[0] < 0  # negative-going


def test_impulse_centroid_is_the_ramp_within_support():
    """Inside the window support the raw centroid is the antisymmetric ramp.

    For a lone spike the centroid reduces to ``ramp[j] = (gw-1)/2 - j``, which
    descends by exactly 1 per sample. Smoothing by a normalized kernel
    preserves that unit slope in the interior, so over the support (away from
    the smoothed edges, and away from the region where the guarded denominator
    makes the ratio 0 rather than the ramp) the centroid is linear with slope
    -1. That pins the ramp's magnitude and sign independently of the fixture.
    """
    fs = 16000.0
    n = 4000
    p = 2000
    u = np.zeros(n)
    u[p] = 1.0
    cfg = gd.GroupDelayConfig()
    gw = gd.odd_window_length(cfg.gw_len, fs)
    result = gd.energy_weighted_group_delay(u, fs, cfg)

    # Support is centroid indices [p-(gw-1), p]; take the interior with a
    # margin past the smoothing window on each side.
    fw = gd.odd_window_length(cfg.fw_len, fs)
    margin = fw + 1
    interior = np.arange(p - gw + 1 + margin, p - margin)
    np.testing.assert_allclose(np.diff(result.centroid[interior]), -1.0, atol=1e-9)
