"""Capture the native-fs reference FLOW (u/uu) for a weighted-LP GIF method.

The end-to-end golden the method commits validate against: the capture gate
(capture_gif_weights) pinned the weight and the AR solve; this pins ``u``/``uu``
through the inverse filter and de-emphasis, via the same path cp captured
(``capture_gif_flow.m`` reuses cp's ``lpcifilt`` + de-emph). Writes
``<name>.<method>_flow.npz`` per fixture.

Run per method as its commit lands (AME first). Not run in CI. Requires MATLAB +
a reference-tree checkout and VOICEBOX; paths from environment variables.

Usage:
    python tests/golden/capture/capture_gif_flow.py [method]   # default: ame
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import scipy.io
from refpaths import require_reference_dir, require_reference_file

REPO = Path(__file__).resolve().parents[3]
GOLDEN = REPO / "tests" / "golden"

MATLAB = require_reference_file("VOICEKIT_MATLAB", "the MATLAB executable")
REFERENCE = require_reference_dir(
    "VOICEKIT_REFERENCE_DIR", "the reference tree root providing the weighting constructor"
)
VOICEBOX = require_reference_dir("VOICEKIT_VOICEBOX", "the VOICEBOX toolbox checkout")

FIXTURE_NAMES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def main(method: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for name in FIXTURE_NAMES:
            z = np.load(GOLDEN / f"{name}.npz")
            in_mat = scratch / f"{name}_in.mat"
            out_mat = scratch / f"{name}_flow.mat"
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
                f"capture_gif_flow('{in_mat}','{out_mat}','{method}');"
            )
            subprocess.run([str(MATLAB), "-batch", cmd], check=True)

            m = scipy.io.loadmat(out_mat, squeeze_me=True)
            np.savez_compressed(
                GOLDEN / f"{name}.{method}_flow.npz",
                u=np.asarray(m["u"], dtype=np.float64).ravel(),
                uu=np.asarray(m["uu"], dtype=np.float64).ravel(),
                tstart=np.asarray(m["tstart"], dtype=np.int64).ravel() - 1,  # -> 0-based
            )
            print(f"wrote {name}.{method}_flow.npz")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ame")
