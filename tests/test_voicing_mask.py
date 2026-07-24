"""Unit tests for apply_voicing_mask -- the derived per-cycle mask.

Synthetic known-value: a hand-built VoicingTrack and a tiny VoiceFeatures, so the
reason precedence, the eight-feature subset, the kept structural fields, and the
nan-over-0.0 composition are pinned directly rather than only through D1's live
path (test_vuv_discriminating.test_d1_voicing_mask_real_path).
"""

import numpy as np

from voicekit.features import apply_voicing_mask
from voicekit.features.result import VoiceFeatures
from voicekit.vuv.decision import VoicingTrack

MASKED = ("f0", "cq", "qoq", "mfdr", "pa", "naq", "h1h2", "hrf")
KEPT = ("framek", "frame_len_ok")


def _feats(n):
    """n cycles, every field finite and distinct so masking is visible."""
    a = np.arange(1.0, n + 1.0)
    return VoiceFeatures(
        f0=a.copy(),
        framek=a.astype(np.int64),
        frame_len_ok=np.ones(n, bool),
        mfdr=a.copy(),
        cq=a.copy(),
        pa=a.copy(),
        naq=a.copy(),
        h1h2=a.copy(),
        hrf=a.copy(),
        qoq=a.copy(),
    )


def _track(voiced, floor_gated, undefined, frame_len=512, hop=160):
    return VoicingTrack(
        voiced=np.array(voiced, bool),
        undefined=np.array(undefined, bool),
        floor_gated=np.array(floor_gated, bool),
        fs=16000,
        frame_len=frame_len,
        hop=hop,
    )


def test_reason_precedence_across_the_four_verdicts():
    # One cycle per verdict, placed at frame centres so frame_index is exact.
    # Frame centre k = k*hop + (frame_len-1)/2 = 160k + 255.5 -> use int near it.
    track = _track(
        voiced=[True, False, False, False],
        floor_gated=[False, True, False, False],
        undefined=[False, False, True, False],
    )
    centres = [int(round(k * 160 + 255.5)) for k in range(4)]
    feats = _feats(4)
    masked, reason = apply_voicing_mask(feats, np.array(centres), track)

    assert list(reason) == ["voiced", "floor", "undefined", "aperiodic"]
    # voiced cycle: untouched; the other three: source features nan'd.
    assert np.isfinite(masked.naq[0])
    for i in (1, 2, 3):
        for name in MASKED:
            assert np.isnan(getattr(masked, name)[i]), (i, name)


def test_floor_takes_precedence_over_undefined_on_a_both_true_frame():
    # Zero-energy frame is BOTH floor_gated and undefined; the reason reports
    # "floor" (silence is the actionable fact), not "undefined".
    track = _track(voiced=[False], floor_gated=[True], undefined=[True])
    _, reason = apply_voicing_mask(_feats(1), np.array([255]), track)
    assert reason[0] == "floor"


def test_structural_fields_are_never_masked():
    track = _track(voiced=[False], floor_gated=[False], undefined=[False])  # aperiodic
    feats = _feats(1)
    masked, _ = apply_voicing_mask(feats, np.array([255]), track)
    for name in KEPT:
        assert np.array_equal(getattr(masked, name), getattr(feats, name)), name


def test_nan_wins_over_the_o1_zero_value_on_overlap():
    # A cycle that is both O1==0 (feature already 0.0, the reference value) and
    # non-voiced must end up nan: no glottal source has no value, degenerate or
    # not. Simulate the composed order -- 0.0 already present, then the mask.
    track = _track(voiced=[False], floor_gated=[False], undefined=[False])
    feats = _feats(1)
    feats = VoiceFeatures(**{**feats.__dict__, "cq": np.array([0.0]), "naq": np.array([0.0])})
    masked, _ = apply_voicing_mask(feats, np.array([255]), track)
    assert np.isnan(masked.cq[0]) and np.isnan(masked.naq[0])


def test_returns_a_new_container_input_unchanged():
    track = _track(voiced=[False], floor_gated=[True], undefined=[False])
    feats = _feats(1)
    before = feats.naq.copy()
    masked, _ = apply_voicing_mask(feats, np.array([255]), track)
    assert masked is not feats
    assert np.array_equal(feats.naq, before)  # not mutated in place


def test_edge_gci_past_last_centre_clamps_to_last_frame():
    # A GCI beyond the final frame centre still belongs to the last frame
    # (frame_index clamps); it must not raise or index out of range.
    track = _track(voiced=[True, False], floor_gated=[False, True], undefined=[False, False])
    huge = 10_000  # well past frame 1's centre
    _, reason = apply_voicing_mask(_feats(1), np.array([huge]), track)
    assert reason[0] == "floor"  # clamped to last frame, which is floor-gated
