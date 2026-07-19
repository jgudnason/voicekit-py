"""Capture the reference VUV feature extractor's outputs for the VUV fixtures (golden master).

Runs the reference VUV feature extractor (VOICEBOX ``lpccovar`` and ``enframe``
on the path) on each committed VUV fixture and writes ``<name>.vuvfeat.npz``
holding the feature matrix ``FM = [Nz Es C1 alp1 Ep]`` and ``T`` -- the per-frame
``[start end]`` (1-based) window bounds the reference used. **MATLAB is the
oracle; nothing here is computed on the Python side.**

The reference VUV feature extractor is deterministic (no RNG -- the
non-determinism in the legacy detector was only in the *decision* stage, C's
GMM), so a re-run reproduces the committed ``FM``/``T`` bit-for-bit. This is what
makes step 7's *features* a capture-and-match milestone like steps 1-6 (see
REFERENCE_NOTES "Step 7 (VUV)").

Not run in CI (needs MATLAB + a reference-tree checkout + VOICEBOX); paths come
from environment variables with no silent default -- an unset variable is a clear
error. The committed ``.vuvfeat.npz`` are the oracle the CI parity test
(``test_vuv_features_parity``) runs against without MATLAB.

Usage:
    python tests/synthetic/capture_vuv_features.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import scipy.io

SYN = Path(__file__).resolve().parent
# The loud-failure path resolver is single-sourced under the golden-capture dir.
sys.path.insert(0, str(SYN.parent / "golden" / "capture"))
from refpaths import require_reference_dir, require_reference_file  # noqa: E402

MATLAB = require_reference_file("VOICEKIT_MATLAB", "the MATLAB executable")
VUV_REFERENCE = require_reference_dir(
    "VOICEKIT_VUV_REFERENCE_DIR", "the reference tree root providing the VUV feature extractor"
)
VOICEBOX = require_reference_dir("VOICEKIT_VOICEBOX", "the VOICEBOX toolbox checkout")

FIXTURES = ["vuv_d1_offset_16k", "vuv_d2_vfric_16k", "vuv_d3_breathy_16k", "vuv_svuvs_16k"]


def main() -> None:
    ref = VUV_REFERENCE / "vus" / "vuvMeasurements.m"
    if not ref.exists():
        raise SystemExit(
            f"reference VUV feature extractor not found at {ref}; "
            f"VOICEKIT_VUV_REFERENCE_DIR ({VUV_REFERENCE}) does not look like the "
            "reference tree."
        )

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        cmd = f"addpath('{VUV_REFERENCE / 'vus'}');addpath('{VOICEBOX}');addpath('{SYN}');"
        for name in FIXTURES:
            cmd += f"capture_vuv_features('{SYN / (name + '.wav')}','{scratch / (name + '.mat')}');"
        subprocess.run([MATLAB, "-batch", cmd], check=True)

        for name in FIXTURES:
            m = scipy.io.loadmat(scratch / f"{name}.mat")
            np.savez_compressed(
                SYN / f"{name}.vuvfeat.npz",
                FM=np.asarray(m["FM"], dtype=np.float64),  # [Nz Es C1 alp1 Ep] per frame
                T=np.asarray(m["T"], dtype=np.int64),  # [start end] 1-based window bounds
                fs=np.asarray(m["fs"], dtype=np.int64).reshape(()),
            )
            print(f"wrote {name}.vuvfeat.npz ({m['FM'].shape[0]} frames)")


if __name__ == "__main__":
    main()
