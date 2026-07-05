"""Drive the MATLAB golden-master capture end to end.

Steps, for each committed fixture under ``data/fixtures/``:

1. Instrument the published ``vsaTools/YAGA/dypsagoi.m`` (see ``instrument.py``)
   into a scratch directory that shadows the reference on the MATLAB path.
2. Run the detector twice via ``capture_one.m``: once with ``opt=''`` (the
   canonical GCIs/GOIs) and once with ``opt='v'`` (to populate the DP
   per-candidate cost decomposition, which the ``'v'`` path computes).
3. Merge both runs and write one ``<fixture>.npz`` under ``tests/golden/``,
   plus a single ``wfilters_bior15.npz`` convention reference.

Nothing here is run in CI. It requires MATLAB + Wavelet/Signal toolboxes and
local checkouts of VOICEBOX and vsaTools; paths are taken from environment
variables (documented in ``tests/golden/README.md``) with sensible local
defaults, never hardcoded into committed algorithm code.

Usage:
    python tests/golden/capture/capture_golden.py
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import scipy.io

from instrument import apply as instrument_apply

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "data" / "fixtures"
GOLDEN = REPO / "tests" / "golden"

MATLAB = os.environ.get(
    "VOICEKIT_MATLAB", "/Applications/MATLAB_R2024b.app/bin/matlab"
)
VOICEBOX = Path(
    os.environ.get("VOICEKIT_VOICEBOX", Path.home() / "Documents/Current/voicebox/voicebox")
)
VSATOOLS = Path(
    os.environ.get("VOICEKIT_VSATOOLS", Path.home() / "Documents/Current/voicekit/vsaTools")
)

FIXTURE_NAMES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]

# Fields from the canonical (opt='') run that merely duplicate another kept
# array (verified bit-equal); dropped to keep the committed .npz small.
#   gd_r == crnmp; ret_udash/crnmp/gdwav == their intermediates;
#   ret_gci/goi == gci/goi; ret_gcic == dp_gcic.
DEFAULT_DROP = {
    "gd_r", "ret_udash", "ret_crnmp", "ret_gdwav",
    "ret_gci", "ret_goi", "ret_gcic",
}
# Fields kept from the opt='v' run. Its full-length signal arrays are
# bit-identical to the default run, so only the DP cost decomposition (which
# the 'v' path uniquely computes) and the voicing-filtered final GCIs are
# worth keeping, under a ``vus_`` prefix.
VUS_KEEP = {"dp_mycost", "dp_Cfn", "dp_gci_costed", "gci"}

# GOLD fields whose values are per-fixture intermediates we keep. Everything
# is squeezed to plain float64 arrays; MATLAB row/col orientation is
# normalized to 1-D where the field is logically a vector.
VECTOR_FIELDS = {
    "udash", "swa", "swd", "mp", "nmp", "crnmp", "gd_r", "gdwav_raw",
    "gdwav", "sew_raw", "zcr_cand_raw", "pro_cand", "s_used", "fnwav",
    "aencost", "cencost", "dp_gcic", "dp_sew", "dp_Cfn", "dp_mycost",
    "gci_dp", "gci", "goi", "Lo_D", "Hi_D",
    "ret_gci", "ret_goi", "ret_gcic", "ret_goic", "ret_gdwav",
    "ret_udash", "ret_crnmp", "input_s",
}
SCALAR_FIELDS = {"nlev", "nu", "nU", "toff", "input_fs"}


def run_matlab(scratch: Path, fixture_wav: Path, out_mat: Path, opt: str) -> None:
    cmd = (
        f"addpath('{VOICEBOX}');"
        f"addpath('{VSATOOLS}');addpath('{VSATOOLS}/YAGA');"
        f"addpath('{scratch}','-begin');"  # instrumented copy shadows reference
        f"addpath('{Path(__file__).parent}');"
        f"capture_one('{fixture_wav}','{out_mat}','{opt}');"
    )
    subprocess.run([MATLAB, "-batch", cmd], check=True)


def load_gold(mat_path: Path) -> dict[str, object]:
    raw = scipy.io.loadmat(mat_path, squeeze_me=True, struct_as_record=False)
    return {k: v for k, v in raw.items() if not k.startswith("__")}


def to_npz_value(name: str, value: object) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if name in SCALAR_FIELDS:
        return arr.reshape(())
    return np.atleast_1d(arr)


def main() -> None:
    ref = VSATOOLS / "YAGA" / "dypsagoi.m"
    if not ref.exists():
        raise SystemExit(f"reference not found: {ref} (set VOICEKIT_VSATOOLS)")
    GOLDEN.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        (scratch / "dypsagoi.m").write_text(
            instrument_apply(ref.read_bytes()), encoding="latin-1"
        )

        wfilters_saved = False
        for name in FIXTURE_NAMES:
            fixture_wav = FIXTURES / f"{name}.wav"
            merged: dict[str, np.ndarray] = {}
            for opt, tag in [("", "default"), ("v", "vus")]:
                out_mat = scratch / f"{name}_{tag}.mat"
                run_matlab(scratch, fixture_wav, out_mat, opt)
                gold = load_gold(out_mat)
                for k, v in gold.items():
                    if k == "opt":
                        continue
                    if tag == "default":
                        if k in DEFAULT_DROP:
                            continue
                        merged[k] = to_npz_value(k, v)
                    elif k in VUS_KEEP:
                        merged[f"vus_{k}"] = to_npz_value(k, v)
                    if not wfilters_saved and k in ("Lo_D", "Hi_D"):
                        np.savez_compressed(
                            GOLDEN / "wfilters_bior15.npz",
                            **{f: to_npz_value(f, gold[f]) for f in ("Lo_D", "Hi_D")},
                        )
                if tag == "default":
                    wfilters_saved = True
            np.savez_compressed(GOLDEN / f"{name}.npz", **merged)
            print(f"wrote {GOLDEN / (name + '.npz')} ({len(merged)} arrays)")


if __name__ == "__main__":
    main()
