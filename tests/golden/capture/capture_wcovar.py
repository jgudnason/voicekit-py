"""Capture the weighted-covariance weight convention target from v_lpccovar.

Pins the single seam every step-8 weighted-LP GIF method routes through: the
reference VOICEBOX ``v_lpccovar`` weights the per-sample error by ``W^2`` (it
applies ``w`` as ``dm.*w`` / ``sc = s.*w``), whereas ``voicekit.lpc.lpc_covar``
weights the error by its ``weights`` argument linearly. So reproducing the
reference requires passing ``weights = W^2``. This capture is the arbiter that
established that (see REFERENCE_NOTES "GIF weighting convention" and
``tests/test_lpc.py::TestWeightedCovarianceConvention``).

The fixture is deliberately tiny and non-degenerate so W vs W^2 are genuinely
separated (a hand-checkable order-2 system whose signal is NOT exactly fittable;
an exactly-fittable signal, e.g. ``test_exact_recovery_from_impulse_response``,
would make both conventions agree and the probe blind). Three pre-capture checks
enforce non-degeneracy before the reference is run.

Not run in CI. Requires MATLAB + a local VOICEBOX checkout; paths via env vars
(defaults match the other capture scripts here). Writes
``tests/golden/wcovar_weight_convention.npz``.

Usage:
    python tests/golden/capture/capture_wcovar.py
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import scipy.io

REPO = Path(__file__).resolve().parents[3]
GOLDEN = REPO / "tests" / "golden"

MATLAB = os.environ.get("VOICEKIT_MATLAB", "/Applications/MATLAB_R2024b.app/bin/matlab")
VOICEBOX = Path(
    os.environ.get("VOICEKIT_VOICEBOX", Path.home() / "Documents/Current/voicebox/voicebox")
)

ORDER = 2
# Distinct hand-chosen integers, NOT order-2 predictable (check a); not a ramp,
# not impulse-response-like.
S = np.array([1.0, -2.0, 3.0, 1.0, -4.0, 2.0, 5.0])
# Weight over the full signal. Strictly monotone, distinct, non-binary, not a
# global scaling of uniform. Only the predicted samples (indices ORDER..N-1) are
# used by the solve.
W = np.array([1.0, 2.0, 3.0, 5.0, 7.0, 11.0, 13.0])


def pre_capture_checks() -> None:
    """Assert the fixture disambiguates W from W^2. Any failure means a
    degenerate fixture, never that the conventions coincide (they differ
    analytically). Reports each check explicitly."""
    from voicekit.lpc import lpc_covar

    n = len(S)
    past = np.column_stack([S[ORDER - k : n - k] for k in range(1, ORDER + 1)])
    target = S[ORDER:]
    wp = W[ORDER:]

    coef, *_ = np.linalg.lstsq(past, -target, rcond=None)
    resid_norm = float(np.linalg.norm(target + past @ coef))
    m_w = past.T @ (wp[:, None] * past)
    m_w2 = past.T @ (wp[:, None] ** 2 * past)
    d_normal = float(np.max(np.abs(m_w - m_w2)))
    a_w = lpc_covar(S, order=ORDER, weights=W).a
    a_w2 = lpc_covar(S, order=ORDER, weights=W**2).a
    d_a = float(np.max(np.abs(a_w - a_w2)))

    print(f"(a) unweighted-LS residual norm  = {resid_norm:.6g}  (must be > 0)")
    print(f"(b) max|normal_W - normal_W^2|   = {d_normal:.6g}  (must be > 0)")
    print(f"(c) max|lpc_covar(W) - lpc_covar(W^2)| = {d_a:.6g}  (must be > 0)")
    assert resid_norm > 1e-6, "DEGENERATE: signal exactly fittable at order 2"
    assert d_normal > 1e-6, "DEGENERATE: W and W^2 give identical normal equations"
    assert d_a > 1e-6, "DEGENERATE: lpc_covar(W) == lpc_covar(W^2)"


def main() -> None:
    pre_capture_checks()
    GOLDEN.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        in_mat = scratch / "input.mat"
        out_mat = scratch / "out.mat"
        scipy.io.savemat(
            in_mat,
            {
                "s": S.reshape(-1, 1),
                "W": W.reshape(-1, 1),
                "order": float(ORDER),
                "t": np.array([[ORDER + 1.0, float(len(S))]]),
            },
        )
        cmd = (
            f"addpath('{VOICEBOX}');"
            f"addpath('{Path(__file__).parent}');"
            f"capture_wcovar('{in_mat}','{out_mat}');"
        )
        subprocess.run([MATLAB, "-batch", cmd], check=True)
        d = scipy.io.loadmat(out_mat, squeeze_me=True)

    out = {
        "s": S,
        "W": W,
        "order": np.array(float(ORDER)),
        "ar_plain": np.atleast_1d(np.asarray(d["ar_plain"], dtype=np.float64)),
        "e_plain": np.atleast_1d(np.asarray(d["e_plain"], dtype=np.float64)),
        "ar_dc": np.atleast_1d(np.asarray(d["ar_dc"], dtype=np.float64)),
        "e_dc": np.atleast_1d(np.asarray(d["e_dc"], dtype=np.float64)),
        "dc": np.array(float(np.asarray(d["dc"]))),
    }
    np.savez_compressed(GOLDEN / "wcovar_weight_convention.npz", **out)
    print(f"wrote {GOLDEN / 'wcovar_weight_convention.npz'}")


if __name__ == "__main__":
    main()
