"""MATLAB parity for the VUV features -- the oracle the synthetic tests cannot be.

Compares this module's per-frame features against the MATLAB reference VUV feature extractor's
``FM``, captured to ``<name>.vuvfeat.npz`` (see ``capture_vuv_features.py``). Runs
in CI **without** MATLAB -- the committed ``.npz`` is the oracle, regenerable from
a fresh MATLAB run (the reference VUV feature extractor is deterministic).

This is the mechanism that catches a wrong-but-separating ``C1`` (which the
C1-alone floor structurally cannot), and it is what caught the ``alp1``/``Ep``
DC-offset gap the synthetic tests could not. See REFERENCE_NOTES VUV7.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from voicekit.io import read_wav
from voicekit.vuv.features import frame_features_at

SYN = Path(__file__).resolve().parent / "synthetic"
FIXTURES = ["vuv_d1_offset_16k", "vuv_d2_vfric_16k", "vuv_d3_breathy_16k", "vuv_svuvs_16k"]
NAR = 16


def _python_on_reference_windows(name: str) -> tuple[np.ndarray, np.ndarray]:
    golden = np.load(SYN / f"{name}.vuvfeat.npz")
    fm = golden["FM"]  # [Nz Es C1 alp1 Ep] per frame
    windows = golden["T"]  # 1-based [start, end] window bounds
    s = read_wav(SYN / f"{name}.wav").samples
    # PER-WINDOW parity: compute on the reference's OWN T(k,:) windows, NOT the
    # VoicingGrid frames. The reference frames are nar-offset (T starts at nar+1);
    # VoicingGrid's start at 0. This validates the FORMULA, decoupled from the
    # framing choice -- test_vuv_grid covers the grid. "Aligning the frame indices"
    # here would manufacture a spurious mismatch, not fix one.
    py = np.array(
        [frame_features_at(s, int(t0) - 1, int(t1) - int(t0) + 1, NAR) for t0, t1 in windows]
    )  # columns [Nz, Es, C1, alp1, Ep], aligned to FM's columns
    return py, fm


def _assert_column(py: np.ndarray, ml: np.ndarray, *, atol: float | None, name: str) -> None:
    if atol is None:  # exact (nan-aware: assert_array_equal treats nan==nan, -inf==-inf)
        np.testing.assert_array_equal(py, ml, err_msg=name)
        return
    fin = np.isfinite(ml)
    np.testing.assert_array_equal(np.isfinite(py), fin, err_msg=f"{name}: finite pattern")
    np.testing.assert_array_equal(py[~fin], ml[~fin], err_msg=f"{name}: degenerate values")
    np.testing.assert_allclose(py[fin], ml[fin], rtol=0, atol=atol, err_msg=name)


@pytest.mark.parametrize("name", FIXTURES)
def test_features_match_matlab_vuvmeasurements(name: str) -> None:
    py, ml = _python_on_reference_windows(name)

    # Nz: integer zero-crossing count -> exact, cross-platform (no float).
    _assert_column(py[:, 0], ml[:, 0], atol=None, name="Nz")

    # C1: bit-exact vs the oracle (measured 0.0 abs error). It has no linear solve;
    # its dot-products/sqrt round identically here. This is VUV7's headline -- a
    # wrong C1 reading (the broadcast-vs-once and s0 differences are O(1)) is
    # caught. If a future BLAS perturbs the sum ordering, machine-eps is the
    # documented fallback; the O(1)-bug-catching purpose survives either way.
    _assert_column(py[:, 2], ml[:, 2], atol=None, name="C1")

    # Es: machine-eps -- sum of squares + log10, no linear solve.
    _assert_column(py[:, 1], ml[:, 1], atol=1e-12, name="Es")

    # alp1: BLAS-eps -- it flows through the covariance least-squares solve
    # (measured max 3.4e-12; atol 1e-10 for cross-BLAS lstsq headroom). J2
    # treatment: the reason is named so nobody tightens this into a flaky gate.
    _assert_column(py[:, 3], ml[:, 3], atol=1e-10, name="alp1")

    # Ep: BLAS-eps, FURTHER AMPLIFIED. Ep = Es - 10*log10(residual_energy/wl); on
    # near-silent frames the residual energy goes tiny, so 10*log10 magnifies the
    # BLAS-eps of the (near-singular) solve into the largest error of the five
    # (measured max 3.8e-8; atol 1e-6). A real reproduction bug is O(1e-2) -- the
    # DC-offset gap this test caught was 5.7e-2 -- far above this headroom, so it
    # hides nothing while staying robust to the log amplification on silence.
    _assert_column(py[:, 4], ml[:, 4], atol=1e-6, name="Ep")
