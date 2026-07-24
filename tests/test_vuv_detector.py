"""Tests for the voicing rule assembly (`detect_voicing`).

No golden master: the decision layer is define-the-target (VUV7/VUV15), so
synthetic known-value tests are the load-bearing mechanism and the fixtures are
the out-of-sample check.

**Fixture assertions are stratified, never aggregate** (VUV11/VUV5): an
aggregate score would hide exactly the limits this milestone spent its effort
establishing. Two of those limits are asserted here as the ledgered
EXPECTATIONS they are, not as failures:
  - D2's voiced frication reads non-voiced (VUV11's C-prime limit);
  - H2's hum warns and then misclassifies (VUV12's named cost).
"""

import warnings

import numpy as np
import pytest
from tests.synthetic.vuv_fixture import load_conditioning_cases, load_discriminating_fixture

from voicekit.signal import Signal
from voicekit.vuv import VoicingGrid, VuvConfig, detect_voicing

# A mid-range envelope for tests that are not about rho_env's value. It is the
# midpoint of the declared 0.53-0.81 range (docs/vuv_rho_env.md) -- a stated
# convention for testing, NOT a recommended default: the config has none, and
# these tests must not smuggle one in by habit.
MID = VuvConfig(rho_env=0.67)


def _config(**kw):
    return VuvConfig(rho_env=kw.pop("rho_env", 0.67), **kw)


def test_config_requires_rho_env():
    # The declaration is structurally unavoidable: rho_env has no default, so
    # the operating envelope cannot be inherited by accident.
    with pytest.raises(TypeError):
        VuvConfig()  # type: ignore[call-arg]


def test_threshold_is_rho_env_plus_the_white_null_quantile():
    # threshold = rho_env + z(1-alpha)/sqrt(N), the two terms kept apart
    # (docs/vuv_r1_null.md). z(0.95) = 1.6449, N = 512 at 16 kHz.
    cfg = VuvConfig(rho_env=0.6, alpha=0.05)
    assert cfg.threshold(16000.0) == pytest.approx(0.6 + 1.6448536 / np.sqrt(512), rel=1e-6)
    # alpha moves the threshold only ~0.06 across its plausible span, against
    # rho_env's 0.28-wide range: the knob cannot carry the decision.
    span = VuvConfig(rho_env=0.6, alpha=0.001).threshold(16000.0) - cfg.threshold(16000.0)
    assert 0.05 < span < 0.07


def test_constant_signal_is_all_voiced_except_frame_zero():
    # r1 = 1 exactly on a constant frame; every threshold in [-1, 1) admits it.
    sig = Signal(samples=np.ones(4000), fs=16000, source="t")
    track = detect_voicing(sig, _config(enforce_precondition=False))
    assert track.undefined[0]  # frame 0 has no boundary sample
    assert not track.voiced[0]
    assert track.voiced[1:].all()


def test_zero_signal_is_all_undefined_and_never_voiced():
    # r1 = 0/0 = NaN on a zero-energy frame; J1 maps it to non-voiced.
    sig = Signal(samples=np.zeros(4000), fs=16000, source="t")
    track = detect_voicing(sig, _config(enforce_precondition=False))
    assert track.undefined.all()
    assert not track.voiced.any()


def test_track_is_grid_shaped_and_self_describing():
    sig = Signal(samples=np.ones(4000), fs=16000, source="t")
    track = detect_voicing(sig, _config(enforce_precondition=False))
    grid = VoicingGrid()
    assert track.n_frames == len(grid.frame_centers(4000, 16000.0))
    assert (track.frame_centers == grid.frame_centers(4000, 16000.0)).all()
    assert (track.fs, track.frame_len, track.hop) == (16000, 512, 160)


def test_full_scale_signal_is_never_floor_gated():
    # A 0.95-amplitude constant is ~ -0.4 dBFS, nowhere near the -90 dBFS floor.
    sig = Signal(samples=np.full(4000, 0.95), fs=16000, source="t")
    assert not detect_voicing(sig, _config(enforce_precondition=False)).floor_gated.any()


def test_digital_silence_is_floor_gated_and_never_voiced():
    # J2's core case: a below-the-floor frame reads non-voiced and flags
    # floor_gated. Exact-zero silence trips J1 too (0/0), so this is one of the
    # both-true frames -- assert the floor-gating specifically.
    sig = Signal(samples=np.zeros(4000), fs=16000, source="t")
    track = detect_voicing(sig, _config(enforce_precondition=False))
    assert track.floor_gated.all()
    assert not track.voiced.any()


def test_near_silence_is_floor_gated_but_not_undefined_j2_catches_what_j1_misses():
    # The case that proves J2 is not redundant with J1: +-1 LSB dithered silence
    # (~ -92 dBFS RMS) has FINITE r1, so J1 does not fire -- but it is below the
    # -90 dBFS floor, so J2 does. This is why the fields are separate.
    rng = np.random.default_rng(0)
    x = rng.integers(-1, 2, 4000).astype(np.float64) * 2**-15  # ~ -92 dBFS
    track = detect_voicing(
        Signal(samples=x, fs=16000, source="t"), _config(enforce_precondition=False)
    )
    interior = ~track.undefined  # exclude frame 0
    assert track.floor_gated[interior].all()  # J2 fires
    assert not track.undefined[interior].any()  # J1 does not (r1 is finite)
    assert not track.voiced.any()


def test_floor_guard_wins_over_a_sub_floor_periodic_frame():
    # r1 is scale-invariant, so a very quiet periodic frame can clear the
    # threshold. The guard must win: below the floor we do not trust the content.
    fs = 16000
    t = np.arange(4000) / fs
    x = 2**-16 * np.sin(2 * np.pi * 200.0 * t)  # periodic (r1 ~ 1) but ~ -96 dBFS
    track = detect_voicing(
        Signal(samples=x, fs=fs, source="t"), _config(enforce_precondition=False)
    )
    assert track.floor_gated.all()
    assert not track.voiced.any()  # not voiced despite high r1


def test_floor_dbfs_default_is_the_16bit_lsb():
    # Rule-1 note: the default is the 16-bit LSB amplitude, a physical constant
    # fixed before any fixture outcome and unmovable by the ~53 dB margin.
    assert VuvConfig(rho_env=0.67).floor_dbfs == -90.0


def test_voiced_implies_neither_diagnostic_fired():
    for name in ("vuv_d1_offset_16k", "vuv_d3_breathy_16k"):
        fx = load_discriminating_fixture(name)
        t = detect_voicing(fx.signal, MID)
        assert not (t.voiced & (t.undefined | t.floor_gated)).any(), name


def test_anti_creep_the_floor_guard_never_fires_on_d1():
    # The ratified anti-creep guard (VUV1): D1's floor is a REAL noise floor
    # (-37.3 dBFS RMS), 53 dB above the guard, so a floor guard that fired there
    # would be arbitrating speech content. Written before the guard existed; its
    # STAYING green now that the guard lands is the proof the guard did not
    # creep -- guard-before-the-thing-it-guards, working.
    fx = load_discriminating_fixture("vuv_d1_offset_16k")
    assert not detect_voicing(fx.signal, MID).floor_gated.any()


def test_floor_guard_fires_on_no_committed_fixture():
    # The guard's green-in-isolation: nothing changes on any committed fixture,
    # because every fixture floor sits >= ~15 dB above the guard. So the guard's
    # arrival is behaviour-preserving on the whole suite (the digital-silence
    # tests above are its only new firing).
    for name in ("vuv_d1_offset_16k", "vuv_d2_vfric_16k", "vuv_d3_breathy_16k"):
        fx = load_discriminating_fixture(name)
        assert not detect_voicing(fx.signal, MID).floor_gated.any(), name
    for case in load_conditioning_cases():
        cfg = VuvConfig(rho_env=0.67, enforce_precondition=False)
        assert not detect_voicing(case.signal, cfg).floor_gated.any(), case.name


def _region_voiced_fraction(track, fx, kind):
    """Voiced fraction over frames whose FULL WINDOW lies inside the region.

    Not centre-membership: a 512-sample window centred near a boundary carries
    samples from the neighbouring region, so a centre-selected frame is a
    mixture and says nothing about either region. Full containment is also the
    protocol the ledgered per-region r1 values were measured under, so these
    assertions and the record's numbers describe the same frames.

    Boundary frames are therefore unasserted here, deliberately -- they are the
    scorer's problem, and the grid's guard band W = frame_len/2 + hop/2 exists
    for exactly that (VUV6).

    ``undefined`` frames are excluded too, using the track's own diagnostic
    field: their non-voiced verdict is J1's, not the rule's, so counting them
    would mix the two. Frame 0 is always one of them, which otherwise silently
    dilutes any region starting at sample 0.
    """
    i = list(fx.region_kind).index(kind)
    lo, hi = int(fx.region_start[i]), int(fx.region_end[i])
    starts = np.arange(track.n_frames) * track.hop
    sel = (starts >= lo) & (starts + track.frame_len <= hi) & ~track.undefined
    return float(track.voiced[sel].mean())


# --- Fixtures, stratified per region (VUV11/VUV5: never aggregate) -----------


def test_d1_voiced_steady_detected_and_floor_rejected():
    fx = load_discriminating_fixture("vuv_d1_offset_16k")
    t = detect_voicing(fx.signal, MID)
    assert _region_voiced_fraction(t, fx, "voiced_steady") == 1.0
    for kind in ("floor_lead", "floor_trail"):
        assert _region_voiced_fraction(t, fx, kind) == 0.0, kind


def test_d1_decay_tail_loss_is_expected_not_a_failure():
    # VUV5: D1's energy-defeat is asymptotic-in-the-tail. The decay runs
    # SNR 30 -> -2 dB with the label V throughout, so a detector MUST lose the
    # low-SNR end -- that is the fixture's point, provable only under
    # SNR-stratified scoring. Asserted as the ledgered expectation: most of the
    # decay is held, and the sub-floor tail (labelled N) is rejected.
    fx = load_discriminating_fixture("vuv_d1_offset_16k")
    t = detect_voicing(fx.signal, MID)
    assert _region_voiced_fraction(t, fx, "voiced_decay") > 0.5
    assert _region_voiced_fraction(t, fx, "subfloor_residual") < 0.2


def test_d2_voiced_frication_reads_non_voiced_the_ledgered_limit():
    # VUV11's C-prime limit, as a DOCUMENTED PROPERTY of the shipped detector,
    # not a failure: D2's voiced fricative measures r1 = -0.055, below every
    # threshold the declared rho_env range admits, so fixed-threshold r1
    # systematically labels voiced frication non-voiced. Ledgered as VUV17.
    fx = load_discriminating_fixture("vuv_d2_vfric_16k")
    t = detect_voicing(fx.signal, MID)
    assert _region_voiced_fraction(t, fx, "voiced_modal") == 1.0
    assert _region_voiced_fraction(t, fx, "voiced_fricative") == 0.0  # the limit
    assert _region_voiced_fraction(t, fx, "unvoiced_fricative") == 0.0


def test_d3_aspiration_rejected_across_the_whole_rho_env_range():
    # VUV13's mild instance: aspiration measures r1 = 0.271, below the floor of
    # the declared range (0.53 + 0.073 = 0.603), so it is rejected for EVERY
    # admissible rho_env. Real strong aspiration is not covered at any alpha --
    # that is the physics, not this fixture.
    fx = load_discriminating_fixture("vuv_d3_breathy_16k")
    for rho_env in (0.53, 0.67, 0.81):
        t = detect_voicing(fx.signal, VuvConfig(rho_env=rho_env))
        assert _region_voiced_fraction(t, fx, "aspiration") == 0.0, rho_env
        assert _region_voiced_fraction(t, fx, "modal_voiced") == 1.0, rho_env


def test_d3_breathy_is_conditional_on_the_callers_rho_env():
    # The straddle (docs/vuv_rho_env.md), and with rho_env required it is a
    # property of the CALLER'S CONFIGURATION rather than a fixed limit of the
    # detector.
    #
    # The straddle is TIGHTER than the record's mean-based reading, which this
    # assembly measured and VUV17 now carries: the record read breathy against
    # its region MEAN (0.625) and concluded it survives for rho_env < ~0.537.
    # Per-frame, breathy spans [0.593, 0.661], so at the range's floor the
    # threshold (0.6027) already cuts its lower tail -- breathy is PARTIALLY
    # detected there, never fully. Full detection would need rho_env <= 0.520,
    # OUTSIDE the declared 0.53-0.81 range: no admissible envelope detects
    # breathy voice at HNR ~ 0 completely.
    #
    # Asserted as the structural claim (partial at the floor, none at the
    # midpoint), not as the measured fraction -- pinning 0.83 would be fitting.
    fx = load_discriminating_fixture("vuv_d3_breathy_16k")
    at_floor = _region_voiced_fraction(
        detect_voicing(fx.signal, VuvConfig(rho_env=0.53)), fx, "breathy_voiced"
    )
    at_mid = _region_voiced_fraction(
        detect_voicing(fx.signal, VuvConfig(rho_env=0.67)), fx, "breathy_voiced"
    )
    assert 0.0 < at_floor < 1.0  # partial: the tail is already cut at the floor
    assert at_mid == 0.0


def test_h_series_clean_voiced_detected_and_check_silent():
    cases = {c.name: c for c in load_conditioning_cases()}
    for name in ("vuv_h0_clean_16k", "vuv_h4_lowf0_16k"):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            t = detect_voicing(cases[name].signal, MID)
        assert t.voiced[1:].all(), name


def test_h1_dc_raises_the_detector_refuses():
    # VUV12: DC raises. The detector refuses input it cannot answer correctly
    # rather than answering confidently and wrongly (r1 = 0.86 -> false voiced).
    cases = {c.name: c for c in load_conditioning_cases()}
    with pytest.raises(ValueError, match="DC offset"):
        detect_voicing(cases["vuv_h1_dc_16k"].signal, MID)


def test_h2_hum_warns_then_misclassifies_vuv12s_named_cost():
    # The documented cost of enforcement-tracks-confidence, asserted rather than
    # left as prose: hum only WARNS, so the detector proceeds and calls a
    # non-voiced signal voiced (hum is genuinely periodic -- no threshold at any
    # alpha rejects it; only conditioning does). A loud wrong answer, by design.
    cases = {c.name: c for c in load_conditioning_cases()}
    case = cases["vuv_h2_hum_16k"]
    assert case.label == "N"
    with pytest.warns(UserWarning, match="below 70 Hz"):
        track = detect_voicing(case.signal, MID)
    assert track.voiced[1:].all()  # misclassified, as documented

    # And the remedy works: conditioned, the same signal reads non-voiced.
    from voicekit.vuv import condition

    assert not detect_voicing(condition(case.signal), MID).voiced.any()
