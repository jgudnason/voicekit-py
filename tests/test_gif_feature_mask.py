"""GIF5 completion: closed-phase flow -> features -> rank-deficient cycles NaN'd.

Pins the load-bearing fact the mask's extent rests on (the features consume ``u``,
not ``uu``), then the forward-smear coverage end-to-end on the live glide frame,
valid-cycle invariance, and composition with a prior (VUV-style) mask.
"""

from dataclasses import replace
from pathlib import Path

import numpy as np

from voicekit.features import extract_voice_features
from voicekit.features.extract import (
    _VOICING_MASK_SUBSET,
    apply_cycle_mask,
    apply_invalid_frame_mask,
)
from voicekit.gif import ClosedPhaseConfig, closed_phase_gif
from voicekit.io import read_wav

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"

# u-derived source features (read useg = u/fs): the spectral pair and the pulse
# amplitude / open-close timings. mfdr reads uu; naq reads both.
_U_DERIVED = ("pa", "cq", "qoq", "h1h2", "hrf")


def _cp(name: str):
    z = np.load(GOLDEN / f"{name}.npz")
    sp = np.asarray(z["input_s"], dtype=np.float64)
    fs = float(z["input_fs"])
    gci = np.asarray(z["gci"], dtype=np.int64) - 1
    goic = np.asarray(z["ret_goic"])[:, 0].astype(np.int64) - 1
    result = closed_phase_gif(sp, fs, gci, goic, ClosedPhaseConfig())
    return result, fs, gci


def test_features_consume_u_not_uu() -> None:
    """The u-derived features change with u and are invariant to uu.

    This is the pin the forward-smear coverage rests on: because these features
    read ``u`` (IIR-smeared), a rank-deficient frame taints them forward. If a
    refactor switched them to ``uu`` (local), this fails -- and the mask's extent
    rationale would need revisiting.
    """
    result, fs, gci = _cp("vowel_f0100_16k")  # all-valid: clean flow to perturb
    u, uu = result.u, result.uu
    base = extract_voice_features(u, uu, fs, gci)
    chg_uu = extract_voice_features(u, uu * 1.5, fs, gci)  # change uu only
    chg_u_scale = extract_voice_features(u * 1.5, uu, fs, gci)  # scale u
    chg_u_shape = extract_voice_features(u + 0.1 * np.linspace(0.0, 1.0, u.size), uu, fs, gci)
    # The u-derived source features never read uu: exactly invariant to a uu change.
    # This is the pin -- if a refactor routed any of them through uu (local), the
    # forward-smear coverage would be wrong and this would fail.
    for name in _U_DERIVED:
        np.testing.assert_array_equal(getattr(base, name), getattr(chg_uu, name))
    # The u/uu split is real, not a degenerate coincidence: mfdr (a derivative
    # feature) does move with uu, and the u-features move with u (pa with scale,
    # h1h2 with shape -- the ratio features are scale-invariant but not shape-invariant).
    assert not np.allclose(base.mfdr, chg_uu.mfdr, equal_nan=True)
    assert not np.allclose(base.pa, chg_u_scale.pa, equal_nan=True)
    assert not np.allclose(base.h1h2, chg_u_shape.h1h2, equal_nan=True)


def test_glide_masks_forward_from_the_invalid_frame() -> None:
    """The rank-deficient frame NaNs its own cycles AND every cycle after it."""
    result, fs, gci = _cp("vowel_glide_16k")
    feats = extract_voice_features(result.u, result.uu, fs, gci)
    masked, reason = apply_invalid_frame_mask(feats, gci, result)

    invalid = np.flatnonzero(~result.frame_valid)
    assert invalid.size == 1  # the one live GIF3 frame
    first = int(result.frame_starts[int(invalid.min())])
    cyc_hi = np.append(gci[1:], result.uu.size)
    expected = cyc_hi > first  # forward smear: cycle end past the first corrupted sample

    np.testing.assert_array_equal(reason == "rank_deficient", expected)
    # forward block: once masked, every later cycle is masked too (the smear reaches
    # the end -- it is not just the invalid frame's local span)
    idx = np.flatnonzero(expected)
    assert idx.size > 1  # more than the invalid frame's own cycle(s)
    assert np.array_equal(idx, np.arange(idx[0], gci.size))  # contiguous to the end
    # the masked cycles' source features are NaN; the rest are finite there
    for name in _VOICING_MASK_SUBSET:
        vals = getattr(masked, name)
        assert np.all(np.isnan(vals[expected]))


def test_valid_cycles_are_unchanged_by_the_mask() -> None:
    result, fs, gci = _cp("vowel_glide_16k")
    feats = extract_voice_features(result.u, result.uu, fs, gci)
    masked, reason = apply_invalid_frame_mask(feats, gci, result)
    keep = reason == "valid"
    for name in _VOICING_MASK_SUBSET:
        np.testing.assert_array_equal(getattr(masked, name)[keep], getattr(feats, name)[keep])


def test_composes_with_a_prior_mask_union_and_order_independent() -> None:
    # A prior (VUV-style) NaN on an early, closed-phase-VALID cycle must survive the
    # closed-phase mask, and the two orders agree -- np.where selects, never clobbers.
    result, fs, gci = _cp("vowel_glide_16k")
    feats = extract_voice_features(result.u, result.uu, fs, gci)
    prior = np.zeros(gci.size, dtype=bool)
    prior[0] = True  # cycle 0 is well before the invalid frame

    # order A: prior mask, then closed-phase
    a = {n: getattr(feats, n).copy() for n in _VOICING_MASK_SUBSET}
    apply_cycle_mask(a, prior, _VOICING_MASK_SUBSET, np.nan)
    fa, _ = apply_invalid_frame_mask(replace(feats, **a), gci, result)
    # order B: closed-phase, then prior mask
    fb0, _ = apply_invalid_frame_mask(feats, gci, result)
    b = {n: getattr(fb0, n).copy() for n in _VOICING_MASK_SUBSET}
    apply_cycle_mask(b, prior, _VOICING_MASK_SUBSET, np.nan)

    for name in _VOICING_MASK_SUBSET:
        va, vb = getattr(fa, name), b[name]
        np.testing.assert_array_equal(va, vb)  # order-independent
        assert np.isnan(va[0])  # the prior mask's cycle survived


def test_8k_runs_and_is_sane() -> None:
    z = np.load(GOLDEN / "vowel_f0120_8k.npz")
    sig = read_wav(FIXTURES / "vowel_f0120_8k.wav")
    gci = np.asarray(z["gci"], dtype=np.int64) - 1
    goic = np.asarray(z["ret_goic"])[:, 0].astype(np.int64) - 1
    result = closed_phase_gif(sig.samples, float(sig.fs), gci, goic, ClosedPhaseConfig())
    feats = extract_voice_features(result.u, result.uu, float(sig.fs), gci)
    masked, reason = apply_invalid_frame_mask(feats, gci, result)
    assert reason.shape == (gci.size,)
    assert set(np.unique(reason).tolist()) <= {"valid", "rank_deficient"}
