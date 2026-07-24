"""agauss (asymmetric Gaussian) weighted-LP GIF: flow golden + MEASURED support.

The capture gate (``test_gif_weight_convention``) pinned agauss's weight and AR
solve; this pins the end-to-end flow ``u``/``uu`` (``<name>.agauss_flow.npz``).

agauss differs from rgauss/AME in ONE way that matters here: its ``max(0, 1 - gg)``
clamp can produce hard zeros where summed neighbour notches drive ``gg > 1``, so its
effective support is NOT full by construction. Whether a frame goes rank-deficient
is therefore a question answered by MEASUREMENT, not guaranteed. On the committed
fixtures the clamp zeros only a handful of samples (3 / 2 / 0) and no frame's nonzero
support falls near the order, so ``frame_valid`` is all-true HERE -- but that is
measured, not constructed. The invalid-frame mask is *live* for agauss (unlike
rgauss/AME, where it is unreachable by construction) though *unreached* on these
fixtures; glide/cp is still the only fixture that actually drives ``frame_valid``
False. Corpus data could clamp harder and reopen the GIF5 path for agauss.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit._matlab_compat import matlab_round
from voicekit.gif.gaussian import agauss_gif

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


def _run(name: str):
    z = np.load(GOLDEN / f"{name}.npz")
    fl = np.load(GOLDEN / f"{name}.agauss_flow.npz")
    sp = np.asarray(z["input_s"], dtype=np.float64)
    fs = float(z["input_fs"])
    gci = np.asarray(z["gci"], dtype=np.int64) - 1  # 0-based; agauss reads gci only
    return agauss_gif(sp, fs, gci), fl, fs


@pytest.mark.parametrize("name", FIXTURES)
def test_flow_parity(name: str) -> None:
    # u/uu reproduce the reference end-to-end. Not bitwise: the covariance solve is
    # BLAS-accumulated and the flow runs through the FIR inverse filter + IIR
    # de-emphasis -- the cp/GIF8 accumulation reason -- so rtol=1e-6, atol=1e-9
    # (observed abs deviation <= 1.0e-12). No rank-deficient frame on any fixture, so
    # the WHOLE flow matches. 8 kHz included (no IAIF route, so no F1 exclusion).
    result, fl, _ = _run(name)
    np.testing.assert_allclose(result.uu, fl["uu"], rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(result.u, fl["u"], rtol=1e-6, atol=1e-9)


@pytest.mark.parametrize("name", FIXTURES)
def test_full_support_measured_not_constructed(name: str) -> None:
    # agauss's clamp CAN zero support, so this is a MEASUREMENT, not a by-construction
    # guarantee. Re-derive the per-frame nonzero support (the same predicted-sample
    # count the core's GIF5 rank check uses) and confirm no frame falls to the model
    # dimension nar+1 -> frame_valid all-true on this fixture.
    result, _, fs = _run(name)
    nar = int(np.ceil(fs / 1000.0))
    wl = int(matlab_round(fs * 0.032))
    supports = [
        int(np.count_nonzero(result.weight[t0 : t0 + wl + 1])) for t0 in result.frame_starts
    ]
    assert min(supports) >= nar + 1  # no frame at/below the model dimension
    assert result.frame_valid.all()  # the core agrees: zero rank-deficient frames here


def test_clamp_is_active_on_16k_and_handled_identically() -> None:
    # The clamp genuinely bites on the 16 kHz fixtures (0 samples on 8k). Confirm it is
    # active -- so this path is exercised -- and that the flow AT the clamped samples
    # matches the reference at the flow tolerance: the clamp lives inside the weight
    # fn, so the capture and voicekit solve on the identical clamped weight. A larger
    # deviation at clamped samples than elsewhere would be a clamp-handling finding.
    for name in ["vowel_f0100_16k", "vowel_glide_16k"]:
        result, fl, _ = _run(name)
        clamped = np.flatnonzero(result.weight == 0.0)
        assert clamped.size > 0  # clamp active on this fixture (3 / 2 samples)
        assert np.max(np.abs((result.uu - fl["uu"])[clamped])) < 1e-9
        assert np.max(np.abs((result.u - fl["u"])[clamped])) < 1e-9


def test_8k_clamp_inactive() -> None:
    # On 8k the clamp bites nothing (measured: 0 samples) -- the weight stays strictly
    # positive there, so support is full for a different reason than on 16k. Recorded
    # so the support story is measured per fixture, not assumed uniform.
    result, _, _ = _run("vowel_f0120_8k")
    assert int((result.weight == 0.0).sum()) == 0
    assert result.weight.min() > 0.0


def test_frame_geometry_matches_reference() -> None:
    result, fl, _ = _run("vowel_f0100_16k")
    np.testing.assert_array_equal(result.frame_starts, fl["tstart"])


@pytest.mark.parametrize("name", FIXTURES)
def test_frame_support_matches_independent_rederivation(name: str) -> None:
    # The published per-frame count (GIF5/GIF12 instrumentation) is validated against
    # the same independent re-derivation the test above uses, rather than trusting the
    # core's own bookkeeping. Publishing the count is what makes the MARGIN from the
    # rank-deficiency boundary observable: `frame_valid` alone collapses "nowhere near
    # degenerate" and "one sample away" into the same True.
    result, _, fs = _run(name)
    wl = int(matlab_round(fs * 0.032))
    expected = [
        int(np.count_nonzero(result.weight[t0 : t0 + wl + 1])) for t0 in result.frame_starts
    ]
    np.testing.assert_array_equal(result.frame_support, expected)
    assert result.model_dim == int(np.ceil(fs / 1000.0)) + 1
    # frame_valid is exactly the collapse of the published count, not a parallel rule
    np.testing.assert_array_equal(result.frame_valid, result.frame_support >= result.model_dim)


@pytest.mark.parametrize("name", FIXTURES)
def test_support_margin_is_large_on_these_fixtures(name: str) -> None:
    # GIF12's measured minima (510 / 511 / 257 against nar+1 = 17 / 17 / 9) restated as
    # an assertion on the published field. Pinned as a MARGIN, not as an equality: the
    # point is that these fixtures sit far from the boundary, which is why they cannot
    # exercise the GIF5 path and why corpus data is what would reopen it.
    result, _, _ = _run(name)
    assert result.frame_support.min() > 10 * result.model_dim
