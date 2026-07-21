"""Closed-phase weighted-LP GIF: native-fs golden master + GIF5 handling.

Golden-mastered against the reference closed-phase method captured at native fs
(``<name>.cp.npz``, from ``capture_cp.py``; GIF7). The weight and reconstructed
GOIs match bit-exactly; the flow matches to a BLAS-accumulated tolerance on VALID
frames. The one rank-deficient frame on ``vowel_glide_16k`` (GIF3) is where GIF5
lives: voicekit flags it invalid and its flow *diverges* from the reference there
(reference basic solution vs voicekit min-norm, both finite) -- asserted as an
expected divergence, not papered over. 8 kHz is F1 (live IAIF), not captured here.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.gif import ClosedPhaseConfig
from voicekit.gif.closed_phase import closed_phase_gif
from voicekit.io import read_wav

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _run(name: str):
    z = np.load(GOLDEN / f"{name}.npz")
    cp = np.load(GOLDEN / f"{name}.cp.npz")
    sp = np.asarray(z["input_s"], dtype=np.float64)
    fs = float(z["input_fs"])
    gci = np.asarray(z["gci"], dtype=np.int64) - 1  # 0-based
    goic = np.asarray(z["ret_goic"])[:, 0].astype(np.int64) - 1
    result = closed_phase_gif(sp, fs, gci, goic, ClosedPhaseConfig())
    return result, cp


def _valid_sample_mask(result) -> np.ndarray:
    """Samples belonging to a valid frame's inverse-filter output span."""
    n = result.uu.size
    starts = result.frame_starts
    ok = np.ones(n, dtype=bool)
    for i in np.flatnonzero(~result.frame_valid):
        lo = int(starts[i])
        hi = int(starts[i + 1]) if i + 1 < starts.size else n
        ok[lo:hi] = False
    return ok


@pytest.mark.parametrize("name", ["vowel_f0100_16k", "vowel_glide_16k"])
def test_weight_and_goi_bit_exact(name: str) -> None:
    result, cp = _run(name)
    np.testing.assert_array_equal(result.weight, cp["cp_w"])
    np.testing.assert_array_equal(result.goi, cp["cp_goi"])
    np.testing.assert_array_equal(result.frame_starts, cp["cp_tstart"])


@pytest.mark.parametrize("name", ["vowel_f0100_16k", "vowel_glide_16k"])
def test_uu_parity_on_valid_frames(name: str) -> None:
    # uu reproduces the reference on valid-frame samples. Not bitwise: the
    # covariance solve is BLAS-accumulated (varies across hardware), same as the
    # IAIF residual join -- assert at rtol=1e-6, well above the ~1e-11 observed.
    # uu's rank-deficient-frame divergence is LOCAL (an FIR inverse filter, so it
    # confines to that frame's output span), which is why the valid mask suffices.
    result, cp = _run(name)
    ok = _valid_sample_mask(result)
    np.testing.assert_allclose(result.uu[ok], cp["cp_uu"][ok], rtol=1e-6, atol=1e-9)


@pytest.mark.parametrize("name", ["vowel_f0100_16k", "vowel_glide_16k"])
def test_u_parity_up_to_first_invalid_frame(name: str) -> None:
    # u = de-emphasise(uu) is a CAUSAL IIR (5 Hz pole ~0.998, slow decay), so a
    # rank-deficient frame's uu divergence smears FORWARD in u: u matches the
    # reference only up to the first invalid frame's start, and is IIR-tainted
    # after. (f0100 has no invalid frame -> the whole signal matches.) This
    # forward taint is why the downstream GIF5 mask is conservative; see the
    # frame->cycle mapping and REFERENCE_NOTES GIF5.
    result, cp = _run(name)
    invalid = np.flatnonzero(~result.frame_valid)
    end = int(result.frame_starts[int(invalid[0])]) if invalid.size else result.u.size
    np.testing.assert_allclose(result.u[:end], cp["cp_u"][:end], rtol=1e-6, atol=1e-9)


def test_f0100_has_no_rank_deficient_frame() -> None:
    result, _ = _run("vowel_f0100_16k")
    assert result.frame_valid.all()  # every frame full-rank


def test_glide_rank_deficient_frame_flagged_and_diverges() -> None:
    # GIF3/GIF5: exactly one glide frame is rank-deficient. voicekit flags it and
    # its flow diverges from the reference there (min-norm vs basic solution), both
    # finite -- the honest GIF5 divergence, not a NaN.
    result, cp = _run("vowel_glide_16k")
    invalid = np.flatnonzero(~result.frame_valid)
    assert invalid.size == 1  # one rank-deficient frame (per GIF3)
    i = int(invalid[0])
    lo = int(result.frame_starts[i])
    hi = int(result.frame_starts[i + 1])
    span = np.abs(result.uu[lo:hi] - cp["cp_uu"][lo:hi])
    assert span.max() > 1e-3  # genuinely diverges (not just numerical noise)
    assert np.all(np.isfinite(result.uu))  # flow stays finite everywhere (Option B)
    assert np.all(np.isfinite(result.u))


def test_8k_runs_and_is_sane_not_parity() -> None:
    # 8 kHz has no cp golden (F1: live IAIF differs from the capture's clean
    # residual). The method still runs end-to-end and gives a finite, sane flow.
    z = np.load(GOLDEN / "vowel_f0120_8k.npz")
    sig = read_wav(FIXTURES / "vowel_f0120_8k.wav")
    gci = np.asarray(z["gci"], dtype=np.int64) - 1
    goic = np.asarray(z["ret_goic"])[:, 0].astype(np.int64) - 1
    result = closed_phase_gif(sig.samples, float(sig.fs), gci, goic, ClosedPhaseConfig())
    assert result.uu.shape == sig.samples.shape
    assert np.all(np.isfinite(result.uu))
    assert set(np.unique(result.weight).tolist()) <= {0.0, 1.0}
