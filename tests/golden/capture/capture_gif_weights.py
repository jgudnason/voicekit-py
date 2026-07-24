"""Capture native-fs reference weight + per-frame AR for the three continuous-weight
GIF methods (AME, rgauss, agauss) -- the GIF1 two-sided convention gate.

This is the FIRST live exercise of the GIF1 W-vs-W^2 convention. cp's 0/1 mask made
W^2==W (GIF1 a structural no-op, so cp's capture was one-sided, positive only). These
weights are continuous, so W and W^2 give provably different AR -- a real negative
control exists. So each captured frame supports a TWO-SIDED check downstream:

  POSITIVE: lpc_covar(weights = W^2) reproduces the reference AR (machine-eps).
  NEGATIVE: lpc_covar(weights = W)   diverges from the reference AR (the control).

Per fixture, for each method, captures the reference weight vector W (authoritative
weightsForLP) and the reference AR from v_lpccovar (the pinned v_-prefixed oracle;
the unprefixed lpccovar alias DIFFERS and is not the oracle) on every analysis frame,
plus the pre-emphasised signal spp so the Python side solves on IDENTICAL samples
(isolating the QR solve from preemph reproduction). Writes ``<name>.gifw.npz``.

A post-capture non-degeneracy check enforces, per fixture per method, that the
captured frames genuinely separate W from W^2 (GIF1's pre-capture-gate discipline,
here applied to the captured reference W): some frame is full-rank AND
lpc_covar(W).a != lpc_covar(W^2).a by a wide margin. A capture that fails this would
be a zero-evidence pass (the scale-invariance trap) and is rejected loudly.

Not run in CI. Requires MATLAB + a reference-tree checkout and VOICEBOX; paths from
environment variables, no silent default.

Usage:
    python tests/golden/capture/capture_gif_weights.py
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import scipy.io
from refpaths import require_reference_dir, require_reference_file

from voicekit.lpc import lpc_covar

REPO = Path(__file__).resolve().parents[3]
GOLDEN = REPO / "tests" / "golden"

MATLAB = require_reference_file("VOICEKIT_MATLAB", "the MATLAB executable")
REFERENCE = require_reference_dir(
    "VOICEKIT_REFERENCE_DIR", "the reference tree root providing the weighting constructor"
)
VOICEBOX = require_reference_dir("VOICEKIT_VOICEBOX", "the VOICEBOX toolbox checkout")

# All three fixtures. Unlike cp (16k only -- F1 is a live-IAIF-residual limitation),
# these methods do not touch IAIF, so the 8k weight+AR capture is clean.
FIXTURE_NAMES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]
METHODS = ["ame", "rgauss", "agauss"]


def _frame(spp: np.ndarray, w: np.ndarray, t0: int, nar: int, wl: int):
    """Slice one analysis frame exactly as closed_phase.py does (cp-validated
    geometry): history nar samples before t0, predicted interval [t0, t0+wl]."""
    lo, hi = t0 - nar, t0 + wl + 1
    return spp[lo:hi], w[lo:hi]


def _non_degeneracy_report(z: dict) -> None:
    """Assert the captured frames genuinely separate W from W^2 (GIF1 discipline),
    using the CAPTURED reference W. Loud failure on a zero-evidence capture."""
    spp = z["spp"].ravel()
    tstart0 = z["tstart"].astype(int).ravel() - 1  # -> 0-based
    nar, wl = int(z["nar"]), int(z["wl"])
    for m in METHODS:
        W = z[f"w_{m}"].ravel()
        best_div, full_rank_frames = 0.0, 0
        for t0 in tstart0:
            x, w = _frame(spp, W, int(t0), nar, wl)
            support = int(np.count_nonzero(w[nar:]))
            if support < 2 * nar + 2:
                continue
            full_rank_frames += 1
            a_sq = lpc_covar(x, nar, weights=w**2, dc_offset=True).a
            a_lin = lpc_covar(x, nar, weights=w, dc_offset=True).a
            best_div = max(best_div, float(np.max(np.abs(a_sq - a_lin))))
        print(
            f"    [{m}] full-rank frames={full_rank_frames}/{tstart0.size}  "
            f"max|AR(W^2)-AR(W)|={best_div:.4g}"
        )
        assert full_rank_frames > 0, f"DEGENERATE: no full-rank frame for {m}"
        assert best_div > 0.1, (
            f"DEGENERATE: {m} W and W^2 give ~identical AR on every frame "
            f"(max {best_div:.2e}) -- zero-evidence capture, rejected"
        )


def main() -> None:
    ref = REFERENCE / "Toolbox" / "weightsForLP.m"
    if not ref.exists():
        raise SystemExit(
            f"authoritative weighting constructor not found at {ref}; "
            f"VOICEKIT_REFERENCE_DIR ({REFERENCE}) is not the reference tree."
        )
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for name in FIXTURE_NAMES:
            z = np.load(GOLDEN / f"{name}.npz")
            in_mat = scratch / f"{name}_in.mat"
            out_mat = scratch / f"{name}_gifw.mat"
            scipy.io.savemat(
                in_mat,
                {
                    "sp": np.asarray(z["input_s"], dtype=np.float64).reshape(-1, 1),
                    "fs": float(z["input_fs"]),
                    "gci": np.asarray(z["gci"], dtype=np.float64).reshape(1, -1),  # 1-based
                    "goic": np.asarray(z["ret_goic"])[:, 0].astype(np.float64).reshape(-1, 1),
                },
            )
            cmd = (
                f"addpath('{REFERENCE}/Toolbox');addpath('{REFERENCE}');"
                f"addpath('{VOICEBOX}');addpath('{Path(__file__).parent}');"
                f"capture_gif_weights('{in_mat}','{out_mat}');"
            )
            subprocess.run([str(MATLAB), "-batch", cmd], check=True)

            m = scipy.io.loadmat(out_mat, squeeze_me=True)
            out = {
                "spp": np.asarray(m["spp"], dtype=np.float64).ravel(),
                "tstart": np.asarray(m["tstart"], dtype=np.int64).ravel(),  # 1-based
                "tend": np.asarray(m["tend"], dtype=np.int64).ravel(),
                "nar": np.array(int(m["nar"])),
                "wl": np.array(int(m["wl"])),
                "nsp": np.array(int(m["nsp"])),
                "fs": np.array(float(m["fs"])),
            }
            for meth in METHODS:
                out[f"w_{meth}"] = np.asarray(m[f"w_{meth}"], dtype=np.float64).ravel()
                out[f"ar_{meth}"] = np.asarray(m[f"ar_{meth}"], dtype=np.float64)
            print(f"  {name}: non-degeneracy check")
            _non_degeneracy_report(out)
            np.savez_compressed(GOLDEN / f"{name}.gifw.npz", **out)
            print(f"wrote {name}.gifw.npz")


if __name__ == "__main__":
    main()
