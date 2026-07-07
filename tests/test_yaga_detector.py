"""End-to-end tests for the YAGA detector.

Until now every stage was validated on captured inputs (stage isolation). `yaga`
wires the live modules together, so this is the first proof they *compose* -- and
the only exercise of the frame hand-offs (1-based where the DP needs it, 0-based
elsewhere). A single off-by-one there would leave every isolated stage test green
while breaking the pipeline, so the 16 kHz end-to-end match is the frame-plumbing
guard.

The 16 kHz fixtures run bit-exact: their captured `udash` is real IAIF output,
which our IAIF reproduces exactly, so the whole pipeline matches the capture. The
8 kHz fixture cannot -- its capture used a clean-residual injection around the
reference IAIF's 8 kHz NaN (see REFERENCE_NOTES "Fixture limitations"), which live
IAIF does not reproduce -- so 8 kHz is checked for a sane result, not exact parity.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.io import read_wav
from voicekit.yaga.detector import GciResult, YagaConfig, _align_goi_to_cycles, yaga

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


@pytest.mark.parametrize("name", ["vowel_f0100_16k", "vowel_glide_16k"])
def test_end_to_end_matches_capture_16k(name):
    """The full pipeline from the raw signal reproduces the captured GCIs and GOIs.

    This is the composition proof and the frame-plumbing guard: IAIF -> SWT ->
    group delay -> psp -> assembly -> costs -> forward -> traceback -> refine (and
    the GOI branch), all live, matching the capture to the sample. GOIs are checked
    against the captured raw goi cleaned to the same per-cycle form.
    """
    d = np.load(GOLDEN / f"{name}.npz")
    result = yaga(read_wav(FIXTURES / f"{name}.wav"))
    # GciResult.gci is 0-based; the capture is 1-based.
    np.testing.assert_array_equal(result.gci + 1, d["gci"].astype(np.int64))
    expected_goi = _align_goi_to_cycles(d["gci"].astype(np.int64), d["goi"].astype(np.float64))
    np.testing.assert_array_equal(result.goi, expected_goi)  # equal_nan by default


def test_end_to_end_8k_runs_and_is_sane():
    """8 kHz runs end-to-end and gives a sensible result, but not the captured one.

    Live IAIF differs from the 8 kHz capture's clean-residual injection, so exact
    parity is impossible here (a documented fixture limitation). We assert only
    that the pipeline completes and produces plausible voiced GCIs.
    """
    d = np.load(GOLDEN / "vowel_f0120_8k.npz")
    result = yaga(read_wav(FIXTURES / "vowel_f0120_8k.wav"))

    assert not np.array_equal(result.gci + 1, d["gci"].astype(np.int64))  # cannot match
    intervals = np.diff(result.gci)
    f0 = 8000.0 / np.median(intervals)
    assert 110.0 < f0 < 130.0  # target 120 Hz
    assert 50 < result.gci.size < 80  # ~0.6 s of voicing at 120 Hz
    # GOIs are produced too, per-cycle aligned (one entry per GCI), openings falling
    # inside their cycles; some cycles may be unfilled (NaN).
    assert result.goi.shape == result.gci.shape
    paired = ~np.isnan(result.goi)
    assert paired.any()  # at least some cycles have an opening
    assert np.all(result.goi[paired] > result.gci[paired])  # opening after closure


def test_result_fields():
    """GciResult carries 0-based GCIs, per-cycle GOIs (float, NaN for absent), and candidates."""
    result = yaga(read_wav(FIXTURES / "vowel_f0100_16k.wav"))
    assert result.gci.min() >= 0  # 0-based
    # GOI is a float array aligned to gci, with NaN (never a -1 sentinel) for absence.
    assert result.goi.dtype == np.float64
    assert result.goi.shape == result.gci.shape
    assert np.isnan(result.goi).any()  # f0100 has unfilled cycles
    assert result.goi[~np.isnan(result.goi)].min() >= 0  # no -1 poison leaks out
    # Classified candidates: positions plus zero-crossing / projected flags.
    assert result.candidates.positions.shape == result.candidates.is_zero_crossing.shape
    assert result.candidates.is_zero_crossing.any()  # some zero-crossing candidates
    assert (~result.candidates.is_zero_crossing).any()  # and some projected ones


def test_corrected_traceback_flag_flows_through():
    """The traceback bug-compat switch reaches the pipeline and changes glide's output."""
    sig = read_wav(FIXTURES / "vowel_glide_16k.wav")
    quirk = yaga(sig, YagaConfig(traceback_force_penultimate=True))
    corrected = yaga(sig, YagaConfig(traceback_force_penultimate=False))
    assert quirk.gci.size == corrected.gci.size + 1


def test_returns_gci_result_type():
    assert isinstance(yaga(read_wav(FIXTURES / "vowel_f0100_16k.wav")), GciResult)
