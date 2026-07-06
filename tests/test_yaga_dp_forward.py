"""Tests for the DP forward pass.

Golden master (sole arbiter): the forward-pass trellis tables against their
captured internal arbiters (`dp_fc`/`dp_ff`/`dp_fpq`/`dp_ffb`/`dp_gsqm`/`dp_gsd`)
on all three fixtures -- the full `(Ncand+1)*nbest`-node arrays, not a path
subset. This validates the recursion independently of the traceback (the
penultimate-candidate quirk lives there, sub-piece 3). Cost floats (`f_c`,
stats) are machine-epsilon; integer backpointers/periods (`f_f`, `f_pq`,
`f_fb`) are exact.

Upstream arrays (`dp_gcic`, `dp_sew`, `vus_dp_Cfn`, `aencost`, `udash`) are fed
as data, and the two path-dependent costs are the committed sub-piece-1 kernels
(called inside the recursion, not reimplemented). The 1210-node trellis is the
coverage; no weak synthetic DP cases are forced.

Two extra checks the spec calls for: the C3 spurt-marking rule (`f_pq==0` node
set matches the capture, in-domain), and that the module's own `g_sqm`/`g_sd`
statistics agree with the kernel's internal ones (closing the double-compute
loop rather than trusting "same formula").
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga.dp_forward import DpConfig, forward_pass, waveform_window_stats
from voicekit.yaga.dp_kernels import WaveformSimilarityConfig, waveform_similarity

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def _run(d):
    return forward_pass(
        positions=d["dp_gcic"][:, 0],
        flags=d["dp_gcic"][:, 1],
        residual=d["udash"],
        phase_slope_cost=d["dp_sew"],
        frobenius_cost=d["vus_dp_Cfn"],
        closed_phase_cost=d["aencost"],
        fs=float(d["input_fs"]),
    )


# --- 1. Golden master (the arbiter) ----------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_forward_tables_match_capture(name):
    """f_c/f_f/f_pq/f_fb/g_sqm/g_sd reproduce the captured trellis (full node arrays)."""
    d = np.load(GOLDEN / f"{name}.npz")
    r = _run(d)

    # Cumulative cost: same Inf pattern (unreached nodes), finite parts to eps.
    np.testing.assert_array_equal(np.isinf(r.f_c), np.isinf(d["dp_fc"]))
    finite = ~np.isinf(r.f_c)
    np.testing.assert_allclose(r.f_c[finite], d["dp_fc"][finite], rtol=1e-9, atol=1e-9)

    # Backpointers and periods are integer -> exact (0-based node + 1 == captured).
    np.testing.assert_array_equal(r.f_f + 1, d["dp_ff"].astype(np.int64))
    np.testing.assert_array_equal(r.f_pq, d["dp_fpq"])
    np.testing.assert_array_equal(r.f_fb + 1, d["dp_ffb"].astype(np.int64))

    # Waveform statistics to machine epsilon.
    np.testing.assert_allclose(r.g_sqm, d["dp_gsqm"], rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(r.g_sd, d["dp_gsd"], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_spurt_marking_matches_capture(name):
    """C3 arbiter: the recursion's f_pq==0 (spurt-start) nodes are exactly the captured set.

    Unlike the sub-piece-1 selected-path check (only spurt starts at k=0,1), this
    is the full trellis, where spurt starts also land on interior candidates --
    so the marking rule is validated in-domain here.
    """
    d = np.load(GOLDEN / f"{name}.npz")
    r = _run(d)
    np.testing.assert_array_equal(np.where(r.f_pq == 0)[0], np.where(d["dp_fpq"] == 0)[0])
    # Confirm the coverage is genuinely in-domain, not only path edges.
    interior = (np.where(d["dp_fpq"] == 0)[0] // DpConfig().nbest) > 2
    assert interior.any()


# --- 2. Stats double-compute consistency (decision 1) ----------------------


def test_module_stats_agree_with_kernel():
    """The module's g_sqm/g_sd give the same similarity value as the kernel's own stats.

    dp_forward computes the waveform-window statistics itself (for the g_sqm/g_sd
    arbiter) while the similarity kernel recomputes them internally. Rather than
    trust "same formula", plug the module's statistics into the similarity
    formula and assert the result equals the kernel's -- so the two computations
    cannot silently drift.
    """
    d = np.load(GOLDEN / "vowel_f0100_16k.npz")
    fs = float(d["input_fs"])
    udash = d["udash"]
    gci = d["gci_dp"].astype(np.int64)
    cfg = WaveformSimilarityConfig()
    r_pos, q_pos = int(gci[5]), int(gci[4])

    from_kernel = waveform_similarity(udash, [r_pos], [q_pos], fs, cfg)[0]

    sqm, sd = waveform_window_stats(udash, np.array([r_pos, q_pos]), fs, cfg)
    nxc = int(np.ceil(cfg.xwlen * fs))
    half = nxc // 2
    wavix = np.arange(-half, half + 2)
    nx2 = wavix.size
    win_r = udash[(r_pos - 1) + wavix]
    win_q = udash[(q_pos - 1) + wavix]
    cross = float((win_r * win_q).sum())
    from_module_stats = -0.5 * (nx2 - 1) / (nx2 - 2) * (cross - sqm[0] * sqm[1]) * sd[0] * sd[1]

    np.testing.assert_allclose(from_module_stats, from_kernel, rtol=1e-12, atol=1e-14)
