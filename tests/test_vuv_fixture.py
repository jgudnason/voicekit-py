"""Integrity of the synthetic V/UV/S fixture and its loader (step 7).

This validates the **fixture itself** and that the loader round-trips the
committed files. It is deliberately *not* a scoring harness: it evaluates no
detector and makes no framing decision (frame-based vs per-cycle). Every check
here is a framing-neutral property of the ground truth — a partition of the
signal, a voiced-only GCI list — that holds regardless of how a future detector
is scored. The scorer, and the framing choice it embodies, are deferred to the
next gate (see ``tests/synthetic/README.md``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SYNTH_DIR = Path(__file__).resolve().parent / "synthetic"
sys.path.insert(0, str(SYNTH_DIR))

from vuv_fixture import DEFAULT_NAME, load_vuv_fixture  # noqa: E402


def test_region_table_partitions_the_signal():
    """The PRIMARY channel tiles [0, n) with contiguous, non-empty S/U/V regions."""
    f = load_vuv_fixture()
    n = f.signal.n_samples
    assert set(f.region_class.tolist()) <= {"S", "U", "V"}
    assert f.region_start[0] == 0
    assert f.region_end[-1] == n
    np.testing.assert_array_equal(f.region_start[1:], f.region_end[:-1])
    assert np.all(f.region_end > f.region_start)


def test_region_layout_is_S_V_U_V_S():
    """The ratified onset→…→offset layout is present, in order."""
    f = load_vuv_fixture()
    assert f.region_class.tolist() == ["S", "V", "U", "V", "S"]


def test_gci_list_is_voiced_only_and_increasing():
    """The SECONDARY channel lands strictly inside V regions and nowhere else."""
    f = load_vuv_fixture()
    assert f.gci.size > 0
    assert np.all(np.diff(f.gci) > 0)
    v_lo = f.region_start[f.region_class == "V"]
    v_hi = f.region_end[f.region_class == "V"]
    inside = np.zeros(f.gci.shape, dtype=bool)
    for lo, hi in zip(v_lo, v_hi, strict=True):
        inside |= (f.gci >= lo) & (f.gci < hi)
    assert np.all(inside), "every GCI must be inside a V region"


def test_level_separation_S_below_U_below_V():
    """Constructed levels give an unambiguous S ≪ U ≪ V energy ordering."""
    f = load_vuv_fixture()

    def rms(cls):
        vals = [
            f.signal.samples[s:e]
            for s, e, c in zip(f.region_start, f.region_end, f.region_class, strict=True)
            if c == cls
        ]
        return float(np.sqrt(np.mean(np.concatenate(vals) ** 2)))

    assert rms("S") < rms("U") < rms("V")


def test_silence_is_a_floor_not_true_zero():
    """Ratified lean 4a: silent regions carry a low noise floor, not zeros."""
    f = load_vuv_fixture()
    for s, e, c in zip(f.region_start, f.region_end, f.region_class, strict=True):
        if c == "S":
            seg = f.signal.samples[s:e]
            assert np.any(seg != 0.0), "silence must be a noise floor, not true zero"


def test_loader_round_trips_committed_files():
    """The loader exposes the committed arrays with the documented dtypes/shapes."""
    f = load_vuv_fixture()
    assert f.name == DEFAULT_NAME
    assert f.fs == f.signal.fs
    assert f.region_start.dtype == np.int64
    assert f.region_end.dtype == np.int64
    assert f.gci.dtype == np.int64
    assert f.region_class.dtype.kind == "U"
    assert f.region_start.shape == f.region_end.shape == f.region_class.shape


def test_committed_bytes_match_a_fresh_regeneration():
    """The committed signal and labels are exactly what the generator produces.

    Guards against the committed artifact drifting from its generator (manual
    edits, stale bytes). Rebuilds in memory only; writes nothing.
    """
    import make_vuv_fixture as gen
    from scipy.io import wavfile

    signal, labels = gen.build(gen.PRIMARY)
    f = load_vuv_fixture()
    # Compare against the raw int16 stored in the committed wav, i.e. exactly
    # what write_wav quantizes (round(x * 32767)). Re-deriving PCM from the
    # loader's scaled float would double-round (read_wav divides by 32768).
    _, pcm_committed = wavfile.read(SYNTH_DIR / f"{DEFAULT_NAME}.wav")
    pcm_fresh = np.round(signal.samples * 32767.0).astype(np.int16)
    np.testing.assert_array_equal(pcm_committed, pcm_fresh)
    np.testing.assert_array_equal(f.region_start, labels["region_start"])
    np.testing.assert_array_equal(f.region_end, labels["region_end"])
    np.testing.assert_array_equal(f.region_class, labels["region_class"])
    np.testing.assert_array_equal(f.gci, labels["gci"])
