"""Tests for the DP traceback and peak-refinement stages.

Both are validated in isolation on captured tables/arrays. The traceback is fed
a `DpForwardResult` reconstructed directly from the captured trellis (not the
live forward pass), so it is tested independently of sub-piece 2.

Stage A asserts two things: (a) the bug-compatible (penultimate) traceback
reproduces captured `gci_dp` on all three fixtures, and (b) the corrected form
(`force_penultimate=False`) reproduces the glide discriminator -- it drops the
one spurious leading GCI (62 vs 63) and is identical on the other two. Test (b)
proves *the* entry-3 quirk was isolated, not merely a path that happens to match.

Stage B asserts the peak-refinement reproduces the captured final `gci`.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga.dp_forward import DpForwardResult
from voicekit.yaga.dp_traceback import refine_gcis, traceback

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def _result_from_capture(d):
    """Reconstruct a DpForwardResult from the captured trellis (0-based node indices)."""
    return DpForwardResult(
        f_c=d["dp_fc"],
        f_f=d["dp_ff"].astype(np.int64) - 1,
        f_pq=d["dp_fpq"],
        f_fb=d["dp_ffb"].astype(np.int64) - 1,
        g_sqm=d["dp_gsqm"],
        g_sd=d["dp_gsd"],
    )


# --- Stage A: traceback -----------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_traceback_reproduces_gci_dp(name):
    """The bug-compatible (penultimate) traceback reproduces captured gci_dp."""
    d = np.load(GOLDEN / f"{name}.npz")
    gci_dp = traceback(
        _result_from_capture(d),
        d["dp_gcic"][:, 0],
        float(d["input_fs"]),
        force_penultimate=True,
    )
    np.testing.assert_array_equal(gci_dp, d["gci_dp"].astype(np.int64))


def test_corrected_traceback_is_the_quirk_discriminator():
    """The corrected form drops the spurious leading GCI on glide, unchanged elsewhere.

    This is what proves the reproduced quirk is the entry-3 bug: forcing the
    penultimate candidate prepends one spurious GCI on vowel_glide_16k that the
    source-specified correction (i = f_fb(Ncand+1)) does not, while the other two
    fixtures are identical either way.
    """
    for name in ["vowel_f0100_16k", "vowel_f0120_8k"]:
        d = np.load(GOLDEN / f"{name}.npz")
        args = (_result_from_capture(d), d["dp_gcic"][:, 0], float(d["input_fs"]))
        quirk = traceback(*args, force_penultimate=True)
        corrected = traceback(*args, force_penultimate=False)
        np.testing.assert_array_equal(quirk, corrected)  # no difference here

    d = np.load(GOLDEN / "vowel_glide_16k.npz")
    args = (_result_from_capture(d), d["dp_gcic"][:, 0], float(d["input_fs"]))
    quirk = traceback(*args, force_penultimate=True)
    corrected = traceback(*args, force_penultimate=False)
    assert quirk.size == corrected.size + 1  # quirk emits one extra
    np.testing.assert_array_equal(corrected, quirk[1:])  # the spurious one is the leading GCI


# --- Stage B: peak-refinement ----------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_refine_reproduces_final_gci(name):
    """Peak-refinement of gci_dp against crnmp reproduces the captured final gci."""
    d = np.load(GOLDEN / f"{name}.npz")
    gci = refine_gcis(d["gci_dp"].astype(np.int64), d["crnmp"])
    np.testing.assert_array_equal(gci, d["gci"].astype(np.int64))
