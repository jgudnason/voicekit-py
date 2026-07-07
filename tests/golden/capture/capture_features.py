"""Capture reference voice-feature outputs for the golden fixtures.

Black-box capture: for each committed YAGA fixture, feed its ``udash`` and ``gci``
to the reference ``vsaTools/extractVoiceFeatures.m`` (with the derived flow ``u``
per ``vsaTools/testSingleFile.m``) and save the ten feature arrays plus ``u`` into
the fixture's ``.npz``, in the raw reference form (length ``len(gci)+1``, zeros for
degenerate cycles). The reference function is called as a black box -- no
instrumentation -- so none of the YAGA step-zero tooling applies here.

Not run in CI. Requires MATLAB (+ Signal Toolbox) and a vsaTools checkout; paths
come from environment variables (see ``tests/golden/README.md``).

Usage:
    python tests/golden/capture/capture_features.py
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
VSATOOLS = Path(
    os.environ.get("VOICEKIT_VSATOOLS", Path.home() / "Documents/Current/voicekit/vsaTools")
)

FIXTURE_NAMES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]

# Feature arrays returned by extractVoiceFeatures, plus the derived flow u.
FEATURE_FIELDS = [
    "u", "mfdr", "cq", "pa", "naq", "f0", "h1h2", "hrf", "qoq", "framek", "vuv",
]


def main() -> None:
    ref = VSATOOLS / "extractVoiceFeatures.m"
    if not ref.exists():
        raise SystemExit(f"reference not found: {ref} (set VOICEKIT_VSATOOLS)")

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        for name in FIXTURE_NAMES:
            d = np.load(GOLDEN / f"{name}.npz")
            # extractVoiceFeatures uses gci as sample indices; the fixture gci is the
            # final (refined) GCIs, matching testSingleFile's usage.
            scipy.io.savemat(
                scratch / f"{name}_in.mat",
                {
                    "udash": d["udash"],
                    "gci": d["gci"].astype(np.float64),
                    "fs": float(d["input_fs"]),
                },
            )
            out_mat = scratch / f"{name}_feat.mat"
            cmd = (
                f"addpath('{VSATOOLS}');"
                f"addpath('{Path(__file__).parent}');"
                f"capture_features('{scratch}','{out_mat}','{name}');"
            )
            subprocess.run([MATLAB, "-batch", cmd], check=True)

            feat = scipy.io.loadmat(out_mat, squeeze_me=True)
            new = {
                f"feat_{k}": np.atleast_1d(np.asarray(feat[k], dtype=np.float64))
                for k in FEATURE_FIELDS
            }
            merged = {k: d[k] for k in d.files}
            merged.update(new)
            np.savez_compressed(GOLDEN / f"{name}.npz", **merged)
            print(f"wrote {name}.npz (+{len(new)} feature arrays, {new['feat_mfdr'].size} cycles)")


if __name__ == "__main__":
    main()
