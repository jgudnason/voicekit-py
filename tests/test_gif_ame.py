"""AME weighted-LP GIF: native-fs end-to-end flow golden + full-support invariants.

The capture gate (``test_gif_weight_convention``) pinned AME's weight and the AR
solve; this pins the end-to-end flow ``u``/``uu`` through the inverse filter and
de-emphasis (``<name>.ame_flow.npz``, from ``capture_gif_flow.py``). AME's weight
attenuates the main-excitation region to a positive floor (``d = 0.01 > 0``) and
never zeros support, so every frame is full-rank (``frame_valid`` all-true) and the
whole flow matches with no GIF5 carve-out -- unlike cp, whose glide fixture has one
rank-deficient frame.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.gif.ame import ame_gif

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def _run(name: str):
    z = np.load(GOLDEN / f"{name}.npz")
    fl = np.load(GOLDEN / f"{name}.ame_flow.npz")
    sp = np.asarray(z["input_s"], dtype=np.float64)
    fs = float(z["input_fs"])
    gci = np.asarray(z["gci"], dtype=np.int64) - 1  # 0-based; AME reads gci only
    result = ame_gif(sp, fs, gci)
    return result, fl


@pytest.mark.parametrize("name", FIXTURES)
def test_flow_parity(name: str) -> None:
    # u/uu reproduce the reference end-to-end. Not bitwise: the covariance solve is
    # BLAS-accumulated and the flow runs through the FIR inverse filter + the IIR
    # de-emphasis -- the same accumulation cp/GIF8 names -- so rtol=1e-6, atol=1e-9
    # (the exact cp tolerance; observed abs deviation <= 1.2e-12, far inside it).
    # AME has no rank-deficient frame, so the WHOLE flow matches: no valid-frame
    # carve-out (contrast cp's glide frame). 8 kHz is included (AME does not route
    # through IAIF, so cp's F1 8k exclusion does not apply).
    result, fl = _run(name)
    np.testing.assert_allclose(result.uu, fl["uu"], rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(result.u, fl["u"], rtol=1e-6, atol=1e-9)


@pytest.mark.parametrize("name", FIXTURES)
def test_ame_has_full_support_every_frame(name: str) -> None:
    # AME's positive floor (d>0) never zeros support -> every frame full-rank. This
    # is why the invalid-frame mask is inherited but never triggered for AME.
    result, _ = _run(name)
    assert result.frame_valid.all()


def test_frame_geometry_matches_reference() -> None:
    # Geometry cross-check: voicekit's 0-based frame starts equal the captured ones.
    result, fl = _run("vowel_f0100_16k")
    np.testing.assert_array_equal(result.frame_starts, fl["tstart"])
