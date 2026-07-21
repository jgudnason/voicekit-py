"""Capture the native-fs closed-phase reference output for the golden fixtures (GIF7).

For each committed 16 kHz YAGA fixture, run the reference closed-phase method at
native fs (via ``capture_cp.m``) on the fixture's ``input_s`` / ``gci`` /
``ret_goic`` -- all already in the golden ``.npz`` -- and write a separate
``<name>.cp.npz`` with the 0/1 weight, reconstructed GOIs, and the flow ``uu``/``u``.

Separate files (not merged into the fixture ``.npz``) so the existing goldens stay
byte-identical. Not run in CI. Requires MATLAB + a reference-tree checkout and
VOICEBOX; paths come from environment variables, no silent default.

Usage:
    python tests/golden/capture/capture_cp.py
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import numpy as np
import scipy.io
from refpaths import require_reference_dir, require_reference_file

REPO = Path(__file__).resolve().parents[3]
GOLDEN = REPO / "tests" / "golden"

MATLAB = require_reference_file("VOICEKIT_MATLAB", "the MATLAB executable")
REFERENCE = require_reference_dir(
    "VOICEKIT_REFERENCE_DIR", "the reference tree root providing the closed-phase method"
)
VOICEBOX = require_reference_dir("VOICEKIT_VOICEBOX", "the VOICEBOX toolbox checkout")

# Native-fs parity only on the 16 kHz fixtures (8 kHz is F1: live IAIF differs).
FIXTURE_NAMES = ["vowel_f0100_16k", "vowel_glide_16k"]


def main() -> None:
    ref = REFERENCE / "Toolbox" / "weightsForLP.m"
    if not ref.exists():
        raise SystemExit(
            f"reference weighting constructor not found at {ref}; VOICEKIT_REFERENCE_DIR "
            f"({REFERENCE}) does not look like the reference tree."
        )
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for name in FIXTURE_NAMES:
            z = np.load(GOLDEN / f"{name}.npz")
            in_mat = scratch / f"{name}_in.mat"
            out_mat = scratch / f"{name}_cp.mat"
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
                f"capture_cp('{in_mat}','{out_mat}');"
            )
            subprocess.run([str(MATLAB), "-batch", cmd], check=True)

            m = scipy.io.loadmat(out_mat, squeeze_me=True)
            np.savez_compressed(
                GOLDEN / f"{name}.cp.npz",
                cp_w=np.asarray(m["w"], dtype=np.float64).ravel(),
                cp_goi=np.asarray(m["goi"], dtype=np.int64).ravel() - 1,  # -> 0-based
                cp_uu=np.asarray(m["uu"], dtype=np.float64).ravel(),
                cp_u=np.asarray(m["u"], dtype=np.float64).ravel(),
                cp_tstart=np.asarray(m["tstart"], dtype=np.int64).ravel() - 1,  # -> 0-based
            )
            print(f"wrote {name}.cp.npz")


if __name__ == "__main__":
    main()
