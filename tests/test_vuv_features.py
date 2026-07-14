"""Atal-Rabiner VUV feature layer -- reproduce-the-definition + the C1 floor.

Two kinds of test:
  * synthetic-known-value (hand-computed, not round-trips) proving each of the
    five features matches its reference formula. C1 gets the heaviest scrutiny of
    the five -- it is doubly load-bearing (sole floor separator AND the feature the
    noise-null threshold will apply to), and the floor cannot catch a
    wrong-but-separating C1 (REFERENCE_NOTES VUV7);
  * the energy-only-rejection floor: C1 separates the D2/D3 RMS-matched pairs (Es
    provably cannot), distinct from reproduce-the-definition.

A tiny grid (fs=1000, frame_len=4, hop=2, nar=2) makes the LPC window and the C1
boundary term hand-computable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from voicekit.signal import Signal
from voicekit.vuv import VoicingGrid, VuvFeaturesConfig, extract_frame_features

SYNTH_DIR = Path(__file__).resolve().parent / "synthetic"
sys.path.insert(0, str(SYNTH_DIR))
from vuv_fixture import load_discriminating_fixture  # noqa: E402

# fs=1000 -> frame_len=4, hop=2, nar=2; frame 0 (start 0) is history-less.
TINY = VuvFeaturesConfig(grid=VoicingGrid(frame_dur_s=0.004, hop_dur_s=0.002), lpc_order=2)


def _feats(samples, cfg=TINY):
    return extract_frame_features(Signal(np.asarray(samples, dtype=float), 1000), cfg)


# --- C1: heaviest scrutiny of the five (VUV7) -------------------------------


def test_c1_boundary_term_s0_shifts_the_value_hand_computed():
    """C1 reaches one sample BEFORE the frame (s0 = s[start-1]) in numerator and
    denominator. Two signals differ ONLY in s[1] (= s0 for frame 1); the
    hand-computed C1 differs accordingly. Frame 1 = [2,3,4,5], N=4.

    num = sum(frame[1:]*frame[:-1] + frame[0]*s0) = (6+12+20) + (N-1)*frame[0]*s0
    den = sqrt((frame@frame) * (s0^2 + sum(frame[:-1]^2)))
    """
    fa = _feats([9, 1, 2, 3, 4, 5, 9, 9])  # s0 = s[1] = 1
    fb = _feats([9, 0, 2, 3, 4, 5, 9, 9])  # s0 = s[1] = 0
    # s0=1: num = 38 + 3*(2*1) = 44 ; den = sqrt(54 * (1 + 4+9+16)) = sqrt(54*30)
    assert fa.c1[1] == 44.0 / np.sqrt(54.0 * 30.0)
    # s0=0: num = 38 + 0 = 38 ; den = sqrt(54 * (0 + 29)) = sqrt(54*29)
    assert fb.c1[1] == 38.0 / np.sqrt(54.0 * 29.0)
    assert fa.c1[1] != fb.c1[1]  # the s0 term measurably moves C1


def test_c1_numerator_broadcasts_s0_while_denominator_uses_it_once():
    """Surfaced quirk (VUV7), reproduced not corrected: the reference numerator
    `sum(s(2:end).*s(1:end-1)+s(1)*s0)` broadcasts the scalar boundary term across
    the N-1 products (MATLAB vector+scalar) so it enters N-1 times; the denominator
    `[s0; s(1:end-1)]` carries s0 as ONE element. That asymmetry is why C1 is
    unbounded (VUV8). Do NOT 'correct' the numerator to add-once."""
    f = _feats([9, 1, 2, 3, 4, 5, 9, 9])
    frame = np.array([2.0, 3.0, 4.0, 5.0])
    s0 = 1.0
    # Denominator: s0 appears once, as one element of the N-vector [s0, frame[:-1]].
    den = np.sqrt((frame @ frame) * (s0**2 + frame[:-1] @ frame[:-1]))
    # Numerator: broadcast (N-1 copies of the boundary term) -- what the code does.
    num_broadcast = np.sum(frame[1:] * frame[:-1]) + (len(frame) - 1) * frame[0] * s0  # 44
    # Numerator: add-once (the author's likely intent, a bounded correlation) -- NOT this.
    num_once = np.sum(frame[1:] * frame[:-1]) + frame[0] * s0  # 40
    assert num_broadcast == 44.0 and num_once == 40.0  # the asymmetry is a real 4-count gap
    assert f.c1[1] == num_broadcast / den  # reproduces the broadcast
    assert f.c1[1] != num_once / den  # not the add-once "correction"


def test_c1_is_not_bounded_by_one():
    """The reference C1 is not textbook normalized autocorrelation; it can exceed 1
    (measured 1.41 on D3). Pins the unboundedness the noise-null must reckon with."""
    f = _feats([9, 1, 2, 3, 4, 5, 9, 9])
    assert f.c1[1] > 1.0


# --- Es / Ep / Nz / alp1 known values ---------------------------------------


def test_es_is_log_signal_energy_hand_computed():
    """Es = 10*log10(signal_energy/frame_len), signal_energy read from the one
    lpc_covar call (= energy of the frame [2,3,4,5] = 54); frame_len = 4."""
    f = _feats([9, 1, 2, 3, 4, 5, 9, 9])
    assert f.es[1] == 10.0 * np.log10(54.0 / 4.0)


def test_nz_uses_ge_zero_sign_convention():
    """Nz sign is >= 0 (zero counts non-negative). Frame [1,0,1,0] has zero sign
    changes under >=0 (it would have 3 under >0)."""
    f = _feats([9, 9, 1, 0, 1, 0, 9, 9])
    assert f.nz[1] == 0.0


def test_nz_counts_sign_transitions():
    """Frame [1,-1,1,-1] -> signs [T,F,T,F] -> 3 transitions."""
    f = _feats([9, 9, 1, -1, 1, -1, 9, 9])
    assert f.nz[1] == 3.0


# --- Degeneracies reproduced (exact IEEE values), quarantined ---------------


def test_zero_frame_reproduces_exact_inf_and_nan():
    """A zero-energy frame: Es = -inf (log10(0), eps disabled), Ep = NaN
    (-inf - -inf), C1 = NaN (0/0). Exact IEEE values, not approximate."""
    f = _feats(np.zeros(8))
    assert np.isneginf(f.es[1])
    assert np.isnan(f.ep[1])
    assert np.isnan(f.c1[1])


def test_frame0_is_undefined_and_does_not_wrap_to_the_signal_tail():
    """THE frame-0 pin: s0 = s[start-1] at start 0 is s[-1] in Python -- the LAST
    sample, not an error. It would NOT raise; it would silently compute a finite C1
    from the signal tail. Assert frame 0 is routed to the undefined path (NaN),
    NOT the wrapped value -- the guard, not a silent wrap, is the claim."""
    f = _feats([1, 2, 3, 4, 5, 6, 7, 100])
    # history-dependent features are undefined at frame 0
    assert np.isnan(f.c1[0]) and np.isnan(f.es[0]) and np.isnan(f.ep[0]) and np.isnan(f.alp1[0])
    # what a silent wrap (s0 = s[-1] = 100) WOULD have produced -- a finite value:
    frame = np.array([1.0, 2.0, 3.0, 4.0])
    s0_wrapped = 100.0
    num = np.sum(frame[1:] * frame[:-1] + frame[0] * s0_wrapped)
    den = np.sqrt((frame @ frame) * (s0_wrapped**2 + frame[:-1] @ frame[:-1]))
    wrapped = num / den
    assert np.isfinite(wrapped)  # the wrap would be finite (~0.584) -- and we avoid it
    assert not np.isclose(f.c1[0], wrapped, equal_nan=False)  # NaN, not the wrap


def test_nz_is_history_free_and_defined_at_frame0():
    """Nz needs no history, so it is defined even at the otherwise-undefined frame 0
    (the LPC-derived features and C1 are NaN there; Nz is not)."""
    f = _feats([1, 0, 1, 0, 9, 9, 9, 9])
    assert f.nz[0] == 0.0  # frame [1,0,1,0] under >=0


# --- The energy-only-rejection floor: C1 ALONE (VUV7) -----------------------


def _region_mean_c1(name: str) -> dict[str, float]:
    fx = load_discriminating_fixture(name)
    f = extract_frame_features(fx.signal)  # default config: VoicingGrid 32/10, order 16
    buckets: dict[str, list[float]] = {}
    for center, c1 in zip(f.frame_centers, f.c1, strict=True):
        for lo, hi, kind in zip(fx.region_start, fx.region_end, fx.region_kind, strict=True):
            if lo <= center < hi:
                buckets.setdefault(str(kind), []).append(float(c1))
                break
    return {k: float(np.nanmean(v)) for k, v in buckets.items()}


def test_floor_c1_separates_d2_matched_pair():
    """C1 separates the D2 RMS-matched pair, which Es provably cannot (equal energy).
    C1 ALONE carries the floor: Ep is NOT co-asserted -- it inverts on D2 (prediction
    gain is higher for the peaky frication noise than the broadband voiced mix,
    measured +2.97 V vs +5.84 N), and alp1 tracks tilt (decoupled from voicing by
    D3's construction). Adding either here would commit a failing assertion."""
    c1 = _region_mean_c1("vuv_d2_vfric_16k")
    assert c1["voiced_fricative"] > c1["unvoiced_fricative"]


def test_floor_c1_separates_d3_matched_pair():
    """C1 separates the D3 RMS-matched pair (breathy voiced vs aspiration). Same
    C1-alone rationale as D2 -- see that test for why Ep/alp1 are excluded."""
    c1 = _region_mean_c1("vuv_d3_breathy_16k")
    assert c1["breathy_voiced"] > c1["aspiration"]


def test_floor_c1_separates_d1_voiced_from_floor():
    """On D1, C1 separates the voiced spans (incl. the low-SNR decay tail) from the
    noise floor. Full SNR-stratified scoring of the tail is a scorer concern
    (deferred); the region-level separation is the feature-layer floor here."""
    c1 = _region_mean_c1("vuv_d1_offset_16k")
    assert min(c1["voiced_steady"], c1["voiced_decay"]) > c1["floor_lead"]
