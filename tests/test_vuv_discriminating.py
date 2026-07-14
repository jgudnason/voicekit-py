"""Discriminating V/non-V fixtures (D1/D2/D3) — integrity and the D1 mask exercise.

Ground-truth and fixture tests only: no classifier, no thresholds. The load-bearing
test here is ``test_d1_mask_exercise_runs_on_live_yaga`` — it asserts, against the
GCIs YAGA *actually detects* on D1, that a real closure lands in a non-voiced
region beyond the (symbolic) guard band, so the derived per-cycle mask's frame
lookup and nan-value assignment are genuinely exercised. That closes the gap the
clean floor fixture left open (its GCIs were all interior-voiced, mask a no-op).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SYNTH_DIR = Path(__file__).resolve().parent / "synthetic"
sys.path.insert(0, str(SYNTH_DIR))

from vuv_fixture import load_discriminating_fixture  # noqa: E402

from voicekit.features import apply_cycle_mask, derive_flow, extract_voice_features  # noqa: E402
from voicekit.vuv.grid import VoicingGrid  # noqa: E402
from voicekit.yaga import yaga  # noqa: E402

D1 = "vuv_d1_offset_16k"

# The guard band W = frame_len/2 + hop/2 is sourced from the locked VoicingGrid
# (32/10 ms) -- single source, no hardcoded durations here. At 16 kHz W = 336.
def _grid_W(fs: int) -> float:
    return VoicingGrid().guard_band_samples(fs)


def _label_at(fx, sample: int) -> str:
    """Ground-truth region label containing ``sample`` (a region-table read)."""
    for lo, hi, lab in zip(fx.region_start, fx.region_end, fx.region_label, strict=True):
        if lo <= sample < hi:
            return str(lab)
    raise AssertionError(f"sample {sample} outside every region")


def _kind_span(fx, kind: str) -> tuple[int, int]:
    idx = int(np.where(fx.region_kind == kind)[0][0])
    return int(fx.region_start[idx]), int(fx.region_end[idx])


def test_d1_region_table_partitions_and_is_binary():
    fx = load_discriminating_fixture(D1)
    n = fx.signal.n_samples
    assert set(fx.region_label.tolist()) <= {"V", "N"}
    assert fx.region_start[0] == 0 and fx.region_end[-1] == n
    np.testing.assert_array_equal(fx.region_start[1:], fx.region_end[:-1])
    assert np.all(fx.region_end > fx.region_start)


def test_d1_construction_closures_span_the_source_on_region():
    """Source closures run from voiced-steady through the sub-floor tail — i.e.
    the construction GCI list is deliberately NOT voiced-only (some land in N)."""
    fx = load_discriminating_fixture(D1)
    steady_lo, _ = _kind_span(fx, "voiced_steady")
    _, src_off = _kind_span(fx, "subfloor_residual")  # source stops at end of sub-floor
    assert np.all((fx.gci_construction >= steady_lo) & (fx.gci_construction < src_off))
    # And at least one construction closure lies in the non-voiced sub-floor tail.
    t3, tso = _kind_span(fx, "subfloor_residual")
    assert np.any((fx.gci_construction >= t3) & (fx.gci_construction < tso))


def test_d1_mask_exercise_runs_on_live_yaga():
    """THE gap-closer: a GCI YAGA actually detects lands in a non-voiced region,
    beyond the symbolic guard band — so the derived per-cycle mask is exercised."""
    fx = load_discriminating_fixture(D1)
    gci = yaga(fx.signal).gcis.gci  # live detector output, not a construction list

    t3, tso = _kind_span(fx, "subfloor_residual")
    W = _grid_W(fx.fs)

    # (1) a detected non-voiced GCI, past the V->N boundary by >= W (outside the
    #     guard band -> an unambiguous non-voiced closure, not a don't-care).
    nonvoiced_beyond_W = [
        int(g) for g in gci if _label_at(fx, int(g)) == "N" and (g - t3) >= W
    ]
    assert nonvoiced_beyond_W, "no detected GCI in a non-voiced region beyond the guard band"
    # boundary case covered: GCI just past the voiced->non-voiced switch.
    assert all(g >= t3 + W for g in nonvoiced_beyond_W)

    # (2) the complementary mask-False branch: a detected voiced GCI exists.
    assert any(_label_at(fx, int(g)) == "V" for g in gci)


@pytest.mark.filterwarnings("ignore:kernel_size exceeds volume extent")
def test_d1_derived_mask_nans_nonvoiced_cycle_keeps_voiced_finite():
    """Downstream of detection: the per-cycle mask (ground-truth track projected
    onto detected cycles) nans a non-voiced cycle's features and leaves a voiced
    cycle's finite. The masked subset is illustrative of the apply_cycle_mask
    seam mechanics; the final subset is a classifier-sub-gate decision."""
    fx = load_discriminating_fixture(D1)
    fs = fx.fs
    res = yaga(fx.signal)
    gci = res.gcis.gci
    u = derive_flow(res.residual, fs)
    feats = extract_voice_features(u, res.residual, fs, gci)

    # Per-cycle mask: cycle i (begins at gci[i]) is masked iff its GCI is in a
    # track-non-voiced region. Track == ground-truth region labels here.
    mask = np.array([_label_at(fx, int(g)) == "N" for g in gci], dtype=bool)

    t3, tso = _kind_span(fx, "subfloor_residual")
    W = _grid_W(fs)
    steady_lo, steady_hi = _kind_span(fx, "voiced_steady")
    subset = ("mfdr", "pa", "naq", "cq", "qoq")

    # a non-voiced cycle beyond W, and a voiced cycle already finite before masking
    i_nonvoiced = next(
        i for i, g in enumerate(gci) if t3 <= g < tso and (g - t3) >= W
    )
    i_voiced = next(
        i
        for i, g in enumerate(gci)
        if steady_lo <= g < steady_hi and np.isfinite(feats.naq[i])
    )
    assert mask[i_nonvoiced]  # mask True on the non-voiced cycle
    assert not mask[i_voiced]  # mask False on the voiced cycle

    raw = {name: getattr(feats, name).copy() for name in subset}
    apply_cycle_mask(raw, mask, subset, np.nan)
    for name in subset:
        assert np.isnan(raw[name][i_nonvoiced]), f"{name} not nan on masked cycle"
    assert np.isfinite(raw["naq"][i_voiced]), "voiced cycle wrongly altered"


def test_d1_exports_snr_stratification_metadata():
    """The per-region hard-regime channel is present and named (SNR for D1)."""
    fx = load_discriminating_fixture(D1)
    assert fx.hard_param_name == "snr_db"
    assert fx.region_hard_param.shape == fx.region_label.shape
    # voiced_steady is the high-SNR anchor; sub-floor is below it.
    steady = fx.region_hard_param[fx.region_kind == "voiced_steady"][0]
    sub = fx.region_hard_param[fx.region_kind == "subfloor_residual"][0]
    assert steady > sub


# --- D2 / D3: matched-pair feature-defeat construction (no classifier) --------

D2 = "vuv_d2_vfric_16k"
D3 = "vuv_d3_breathy_16k"


def _region(fx, kind):
    lo, hi = _kind_span(fx, kind)
    return fx.signal.samples[lo:hi]


def _rms(s):
    return float(np.sqrt(np.mean(s**2)))


def _zcr(s):
    return float(np.mean(np.abs(np.diff(np.sign(s)))) / 2)


def _pitch_lag_ac(s, fs, f0):
    """Normalized autocorrelation at the pitch lag — isolates F0 periodicity from
    broadband spectral smoothness (which a low-tilt/low-pass signal would inflate
    at lag 1). This is the surviving separator the fixtures rely on."""
    lag = int(round(fs / f0))
    s = s - np.mean(s)
    return float(np.sum(s[lag:] * s[:-lag]) / np.sum(s**2))


def _hf_lf(s, fs):
    spec = np.abs(np.fft.rfft(s))
    freq = np.fft.rfftfreq(len(s), 1 / fs)
    return float(np.sum(spec[freq > 3000]) / np.sum(spec[freq <= 3000]))  # spectral-tilt proxy


def test_d2_d3_partition_and_binary_labels():
    for name in (D2, D3):
        fx = load_discriminating_fixture(name)
        n = fx.signal.n_samples
        assert set(fx.region_label.tolist()) <= {"V", "N"}
        assert fx.region_start[0] == 0 and fx.region_end[-1] == n
        np.testing.assert_array_equal(fx.region_start[1:], fx.region_end[:-1])
        assert np.all(fx.region_end > fx.region_start)


def test_d2_d3_construction_closures_are_voiced_only():
    """D2/D3 have no source in non-voiced regions -> closures all land in V."""
    for name in (D2, D3):
        fx = load_discriminating_fixture(name)
        v_lo = fx.region_start[fx.region_label == "V"]
        v_hi = fx.region_end[fx.region_label == "V"]
        inside = np.zeros(fx.gci_construction.shape, dtype=bool)
        for lo, hi in zip(v_lo, v_hi, strict=True):
            inside |= (fx.gci_construction >= lo) & (fx.gci_construction < hi)
        assert np.all(inside)


def test_d2_defeats_energy_exactly_and_bounds_the_zero_crossing_leak():
    """The matched pair (shared turbulence) makes energy *exactly* equal. Zero
    crossings are NOT exactly equal: superimposing the periodic source lowers the
    voiced region's crossing rate by a bounded ~3% (an honest, intrinsic leak, not
    a matched-pair artifact -- see REFERENCE_NOTES VUV3). The surviving separator
    is genuine F0 periodicity (pitch-lag autocorrelation), not lag-1 smoothness."""
    fx = load_discriminating_fixture(D2)
    v, u = _region(fx, "voiced_fricative"), _region(fx, "unvoiced_fricative")
    assert abs(_rms(v) / _rms(u) - 1.0) < 0.005  # energy defeated exactly
    # ZCR leak: voiced strictly below unvoiced, bounded to a few percent.
    assert 0.95 < _zcr(v) / _zcr(u) < 1.0
    # periodicity separates the pair at the pitch lag (voiced positive, unvoiced not).
    assert _pitch_lag_ac(v, fx.fs, 150.0) - _pitch_lag_ac(u, fx.fs, 150.0) > 0.05


def test_d3_defeats_energy_and_tilt_and_breathy_clears_periodicity_bar():
    """Breathy/aspiration are energy-matched (energy defeated); modal vs breathy
    carry different spectral tilt under the same V label (tilt not a proxy). The
    load-bearing check: the *breathy* region (the actual hard case -- weak, tilted,
    HNR~0), not merely modal, is separated from aspiration by genuine F0
    periodicity at the pitch lag."""
    fx = load_discriminating_fixture(D3)
    b, a = _region(fx, "breathy_voiced"), _region(fx, "aspiration")
    assert abs(_rms(b) / _rms(a) - 1.0) < 0.005  # energy defeated exactly
    # spectral tilt differs within the voiced class -> tilt cannot proxy the label
    tilt_modal = _hf_lf(_region(fx, "modal_voiced"), fx.fs)
    tilt_breathy = _hf_lf(_region(fx, "breathy_voiced"), fx.fs)
    assert abs(tilt_modal - tilt_breathy) > 0.05
    # breathy itself clears the periodicity bar at the pitch lag (not just modal).
    assert _pitch_lag_ac(b, fx.fs, 180.0) - _pitch_lag_ac(a, fx.fs, 180.0) > 0.2


def test_d2_d3_export_stratification_metadata():
    assert load_discriminating_fixture(D2).hard_param_name == "vfr_db"
    assert load_discriminating_fixture(D3).hard_param_name == "hnr_db"
