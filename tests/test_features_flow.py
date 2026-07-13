"""Tests for the flow-statistic feature group (mfdr, pa, naq).

Parity (the gate): the raw per-interval mfdr/pa/naq reproduce the captured
reference arrays, all three fixtures, machine-epsilon. Fed the certified captured
u/uu as data. (The reference's O1==0 zeroing is never taken on the fixtures, so
the plain formulas suffice; that coupling to the timing group is applied at
orchestration and is unexercised here.)

Synthetic certification (the flashlight): a hand-computable glottal pulse checks
each formula against a known value. NAQ is the one with a published definition
(Alku): it must equal Alku's f_ac/(d_peak*T) up to the framework period
convention (observation V1) -- ratio exactly period/(period-1). Diagnostic, not a
gate.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.features import extract_voice_features, flow_statistics, prepare_cycles

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def _rosenberg_cycle(period: int) -> np.ndarray:
    t1, t2 = int(0.4 * period), int(0.16 * period)
    pulse = np.zeros(period)
    pulse[:t1] = 0.5 * (1 - np.cos(np.pi * np.arange(t1) / t1))
    pulse[t1 : t1 + t2] = np.cos(np.pi * np.arange(t2) / (2 * t2))
    return pulse


# --- Parity (the gate) ------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_flow_statistics_match_capture(name):
    """Raw mfdr/pa/naq reproduce the captured reference arrays."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci = d["gci"].astype(np.int64) - 1  # 0-based (GciResult convention)
    preps = prepare_cycles(d["feat_u"], d["udash"], gci, fs)
    mfdr, pa, naq = flow_statistics(preps, fs)

    np.testing.assert_allclose(mfdr, d["feat_mfdr"], rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(pa, d["feat_pa"], rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(naq, d["feat_naq"], rtol=1e-12, atol=1e-14)


# --- Synthetic certification (the flashlight) -------------------------------


def test_synthetic_naq_matches_alku_modulo_v1():
    """NAQ equals Alku's f_ac/(d_peak*T) up to the V1 period-1 convention.

    A hand-computable pulse: reference naq = f_ac/(d_peak*(period-1)), which is
    Alku's f_ac/(d_peak*period) scaled by exactly period/(period-1). The 0.63%
    gap at period=160 is observation V1 propagating (naq inherits the framework
    period T = len(nn)-2), not an independent divergence -- so this cross-checks
    V1, it does not open a new observation.
    """
    fs, period = 16000.0, 160
    u = np.tile(_rosenberg_cycle(period), 4)  # several cycles for a clean interior
    uu = np.concatenate([[0.0], np.diff(u)]) * fs
    gci = np.array([period, 2 * period, 3 * period], dtype=np.int64) - 1  # 0-based closures
    _mfdr, _pa, naq = flow_statistics(prepare_cycles(u, uu, gci, fs), fs)

    ref_naq = naq[1]  # interior cycle
    f_ac = u.max() - u.min()
    d_peak = -uu.min()
    alku_naq = f_ac / (d_peak * period)  # Alku, true period
    np.testing.assert_allclose(ref_naq, alku_naq * period / (period - 1), rtol=1e-9)


def test_synthetic_mfdr_and_pa_known_values():
    """MFDR is -min(derivative)/1000; PA is peak-to-peak flow scaled by 1/fs."""
    fs, period = 16000.0, 160
    u = np.tile(_rosenberg_cycle(period), 4)
    uu = np.concatenate([[0.0], np.diff(u)]) * fs
    gci = np.array([period, 2 * period, 3 * period], dtype=np.int64) - 1  # 0-based closures
    mfdr, pa, _naq = flow_statistics(prepare_cycles(u, uu, gci, fs), fs)

    a, b = period, 2 * period  # interior cycle [160, 320], trimmed nn
    nn = np.arange(a, b + 1)
    seg = slice(nn[0] - 1, nn[-1])  # 0-based
    np.testing.assert_allclose(mfdr[1], -uu[seg].min() / 1000.0)
    np.testing.assert_allclose(pa[1], (u[seg].max() - u[seg].min()) / fs)


# --- Shape ------------------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_extract_fills_flow_fields(name):
    """extract_voice_features populates mfdr/pa/naq (this group's fields)."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci0 = d["gci"].astype(np.int64) - 1  # 0-based
    vf = extract_voice_features(d["feat_u"], d["udash"], fs, gci0)

    np.testing.assert_allclose(vf.mfdr, d["feat_mfdr"][1:])  # left-edge dropped
    np.testing.assert_allclose(vf.pa, d["feat_pa"][1:])
    np.testing.assert_allclose(vf.naq, d["feat_naq"][1:])
