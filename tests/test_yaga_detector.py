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
from voicekit.yaga.detector import GciResult, YagaConfig, yaga

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


@pytest.mark.parametrize("name", ["vowel_f0100_16k", "vowel_glide_16k"])
def test_end_to_end_matches_capture_16k(name):
    """The full pipeline from the raw signal reproduces the captured GCIs (bit-exact).

    This is the composition proof and the frame-plumbing guard: IAIF -> SWT ->
    group delay -> psp -> assembly -> costs -> forward -> traceback -> refine, all
    live, matching the captured final gci to the sample.
    """
    d = np.load(GOLDEN / f"{name}.npz")
    result = yaga(read_wav(FIXTURES / f"{name}.wav"))
    # GciResult.gci is 0-based; the capture is 1-based.
    np.testing.assert_array_equal(result.gci + 1, d["gci"].astype(np.int64))


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


def test_result_fields():
    """GciResult carries 0-based GCIs, no GOI (deferred), and the classified candidates."""
    result = yaga(read_wav(FIXTURES / "vowel_f0100_16k.wav"))
    assert result.goi is None
    assert result.gci.min() >= 0  # 0-based
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
