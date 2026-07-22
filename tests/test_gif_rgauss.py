"""rgauss (symmetric Gaussian) weighted-LP GIF: flow golden + full-support invariant.

The capture gate (``test_gif_weight_convention``) pinned rgauss's weight and the AR
solve; this pins the end-to-end flow ``u``/``uu`` (``<name>.rgauss_flow.npz``, from
``capture_gif_flow.py``). rgauss's weight is ``1 - sum kappa*N(gci, sig)``, strictly
positive (minimum ``~ 1 - kappa = 0.1 > 0``), so support is the full frame BY
CONSTRUCTION: ``frame_valid`` is all-true and the whole flow matches with no GIF5
carve-out -- the same category as AME, and unlike agauss (whose clamp can zero
support) or cp (whose glide fixture has one rank-deficient frame).
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.gif.gaussian import rgauss_gif

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def _run(name: str):
    z = np.load(GOLDEN / f"{name}.npz")
    fl = np.load(GOLDEN / f"{name}.rgauss_flow.npz")
    sp = np.asarray(z["input_s"], dtype=np.float64)
    fs = float(z["input_fs"])
    gci = np.asarray(z["gci"], dtype=np.int64) - 1  # 0-based; rgauss reads gci only
    result = rgauss_gif(sp, fs, gci)
    return result, fl


@pytest.mark.parametrize("name", FIXTURES)
def test_flow_parity(name: str) -> None:
    # u/uu reproduce the reference end-to-end. Not bitwise: the covariance solve is
    # BLAS-accumulated and the flow runs through the FIR inverse filter + IIR
    # de-emphasis -- the same accumulation cp/GIF8 names -- so rtol=1e-6, atol=1e-9
    # (the cp tolerance; observed abs deviation <= 1.0e-12, far inside it). rgauss
    # has no rank-deficient frame, so the WHOLE flow matches: no valid-frame
    # carve-out. 8 kHz is included (rgauss does not route through IAIF, so cp's F1
    # 8k exclusion does not apply).
    result, fl = _run(name)
    np.testing.assert_allclose(result.uu, fl["uu"], rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(result.u, fl["u"], rtol=1e-6, atol=1e-9)


@pytest.mark.parametrize("name", FIXTURES)
def test_rgauss_full_support_by_construction(name: str) -> None:
    # rgauss's weight is strictly positive (min ~ 1-kappa = 0.1 > 0), so it can NEVER
    # zero support -- full support by construction, hence frame_valid all-true. The
    # invalid-frame mask is inherited but unreachable for rgauss (contrast agauss,
    # whose clamp can zero samples in principle).
    result, _ = _run(name)
    assert result.weight.min() > 0.0  # strictly positive: no hard zero anywhere
    assert result.frame_valid.all()


def test_frame_geometry_matches_reference() -> None:
    result, fl = _run("vowel_f0100_16k")
    np.testing.assert_array_equal(result.frame_starts, fl["tstart"])
