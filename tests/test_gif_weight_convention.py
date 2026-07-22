"""GIF1 convention, exercised LIVE by continuous weights (AME, rgauss, agauss).

This is the FIRST time the GIF1 W-vs-W^2 convention is confirmed by a live
continuous weight. Every prior weighted test could not disambiguate the
convention, and cp could not either, for a structural reason worth stating so a
later reader does not "simplify" this two-sided test back to cp's one-sided shape:

  - cp's weight is a 0/1 mask, so W^2 == W (idempotent). There is NO wrong
    weighting to diverge -- lpc_covar(W) and lpc_covar(W^2) are identical. cp's
    golden test (test_gif_closed_phase.py) is therefore ONE-SIDED (positive only:
    the flow matches the reference); it structurally cannot carry a negative
    control, and none is missing from it.
  - These three methods have CONTINUOUS weights, so W^2 != W and the two solve
    genuinely different least-squares problems. A negative control finally exists,
    and dropping it would reduce this to the scale-invariance trap GIF1 documents:
    a pass that cannot tell the right weighting from a collapsed one.

So each method's check is TWO-SIDED, both sides against the reference AR captured
by capture_gif_weights.py (weightsForLP -> v_lpccovar, native fs, all frames):

  POSITIVE: lpc_covar(weights = W^2) reproduces the reference AR (machine-eps).
  NEGATIVE (control): lpc_covar(weights = W) diverges from the reference AR on the
            same frame, by an O(1) margin -- asserted, so the test fails if W ever
            starts matching (which would mean the frame went degenerate and the
            positive side proves nothing).

This mirrors the two-sided structure of TestWeightedCovarianceConvention
(capture_wcovar) -- positive W^2 match + negative W divergence -- now on REAL
continuous weights from actual methods rather than a hand-built order-2 toy, and on
the native-fs real-fixture capture shape of capture_cp.

The GIF1 mechanism (survey-pinned from source): v_lpccovar applies the weight to
the residuals (dm.*w, s.*w, then dm\\sc), so W^2 emerges in the normal equations;
reproducing reference weight W means passing lpc_covar(weights = W^2).

Not the full method implementation (weighter module + flow + features + NaN-mask):
that is the next gate. Here we validate the weight construction and the convention.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.gif.ame import ame_weight
from voicekit.lpc import lpc_covar

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]
METHODS = ["ame", "rgauss", "agauss"]

# Positive-side tolerance. The reference AR (MATLAB v_lpccovar, QR/mldivide) and
# lpc_covar (numpy lstsq, SVD) solve the SAME weighted normal equations on the SAME
# captured pre-emphasised samples, so the only gap is QR-vs-SVD floating accumulation
# on an order<=16 real frame -- observed max ~3e-12 across all frames/methods/fixtures.
# Pinned an order of magnitude above that (J2/GIF8-style named reason), still 8 orders
# below the negative control's O(1) divergence.
POSITIVE_ATOL = 1e-10
# Negative control: the wrong (linear-W) convention diverges by O(1). Survey/capture
# measured max|dAR| in [0.70, 3.9]; floored well below the smallest so the control is
# robust yet fails hard (>~10 orders) if the weighting ever collapses to matching.
NEGATIVE_FLOOR = 0.5


# --- reference weight constructions (weightsForLP), reproduced from source for
# --- validation against the captured reference W. gci is 1-based (MATLAB); the
# --- return is length nsp with index i corresponding to sample nn = i+1. These
# --- FORMULAS are what the production weighter module will implement at the next
# --- gate; here they are pinned bit-exact against the reference weight vector.
def rgauss_weight(gci, nsp, fs):
    kappa, sig2 = 0.9, 50.0  # sig = sqrt(50)
    nn = np.arange(1, nsp + 1, dtype=np.float64)
    gg = np.zeros(nsp)
    for g in gci:
        gg += kappa * np.exp(-0.5 * (nn - g) ** 2 / sig2)
    return 1.0 - gg


def agauss_weight(gci, nsp, fs):
    kappa, alpha, r, minF0 = 0.99, 0.1, 2.0, 50.0
    max_spc = 0.5 * np.ceil(fs / minF0)
    nn = np.arange(1, nsp + 1, dtype=np.float64)
    gg = np.zeros(nsp)
    gci_last = max(1.0, float(gci[0]) - max_spc)
    for g in gci:
        n0 = min(float(g) - gci_last, max_spc)
        sig1 = alpha * n0
        sig2 = r * sig1
        gleft = np.exp(-0.5 * (nn - g) ** 2 / sig1**2)
        gleft[nn <= g] = 0.0
        gright = np.exp(-0.5 * (nn - g) ** 2 / sig2**2)
        gright[nn > g] = 0.0
        gg += kappa * (gleft + gright)
        gci_last = float(g)
    return np.maximum(0.0, 1.0 - gg)


# ame_weight is now imported from its production module (voicekit.gif.ame); the
# inline copy was migrated there with the AME method commit. rgauss/agauss remain
# inline until their own method modules are born.
WEIGHT_FN = {"rgauss": rgauss_weight, "agauss": agauss_weight, "ame": ame_weight}


def _load(name):
    return np.load(GOLDEN / f"{name}.gifw.npz")


def _frames(z):
    """0-based frame starts and geometry (matches closed_phase.py / cp)."""
    return z["tstart"].astype(int) - 1, int(z["nar"]), int(z["wl"])


def _frame_slice(spp, w, t0, nar, wl):
    lo, hi = t0 - nar, t0 + wl + 1
    return spp[lo:hi], w[lo:hi]


def _probe_frame(z, method):
    """The max-|dAR| frame -- proven non-degenerate (full-rank, W!=W^2 live). The
    negative control targets this frame; the positive side must also hold on it."""
    spp = z["spp"]
    t0s, nar, wl = _frames(z)
    W, AR = z[f"w_{method}"], z[f"ar_{method}"]
    best_i, best_div = -1, -1.0
    for i, t0 in enumerate(t0s):
        x, w = _frame_slice(spp, W, int(t0), nar, wl)
        a_lin = lpc_covar(x, nar, weights=w, dc_offset=True).a
        div = float(np.max(np.abs(a_lin - AR[i])))
        if div > best_div:
            best_div, best_i = div, i
    return best_i, best_div


@pytest.mark.parametrize("name", FIXTURES)
@pytest.mark.parametrize("method", METHODS)
def test_weight_construction_matches_reference(name: str, method: str) -> None:
    # The reproduced weightsForLP formula is bit-exact against the captured
    # reference weight vector (the weight-construction golden master).
    z = _load(name)
    fz = np.load(GOLDEN / f"{name}.npz")
    gci = np.asarray(fz["gci"], dtype=np.float64)  # 1-based, as the reference uses
    nsp, fs = int(z["nsp"]), float(z["fs"])
    w = WEIGHT_FN[method](gci, nsp, fs)
    ref = z[f"w_{method}"]
    if method == "ame":
        # ame's weight values are exact arithmetic (linear ramps, the floor d, and 1),
        # no transcendentals -> bit-exact against the reference.
        np.testing.assert_array_equal(w, ref)
    else:
        # rgauss/agauss build the weight from exp(): MATLAB's libm and numpy differ at
        # the last ULP (~2e-16 observed), so this is machine-eps, not bit-exact -- the
        # same bit-exact-vs-machine-eps split the port draws elsewhere (cp's 0/1 weight
        # is bit-exact; GIF8's residual is machine-eps for a documented BLAS reason).
        np.testing.assert_allclose(w, ref, atol=1e-14, rtol=0)


@pytest.mark.parametrize("name", FIXTURES)
@pytest.mark.parametrize("method", METHODS)
def test_positive_w_squared_reproduces_reference_all_frames(name: str, method: str) -> None:
    # POSITIVE side, every frame: passing weights = W^2 reproduces the reference AR
    # (the reference applies W to residuals -> W^2 in the normal equations). Uses the
    # CAPTURED reference W, isolating the convention from the weight construction.
    z = _load(name)
    spp = z["spp"]
    t0s, nar, wl = _frames(z)
    W, AR = z[f"w_{method}"], z[f"ar_{method}"]
    for i, t0 in enumerate(t0s):
        x, w = _frame_slice(spp, W, int(t0), nar, wl)
        a = lpc_covar(x, nar, weights=w**2, dc_offset=True).a
        np.testing.assert_allclose(a, AR[i], atol=POSITIVE_ATOL, rtol=0)


@pytest.mark.parametrize("name", FIXTURES)
@pytest.mark.parametrize("method", METHODS)
def test_two_sided_on_probe_frame(name: str, method: str) -> None:
    # The load-bearing two-sided assertion on ONE frame: W^2 matches the reference AR
    # AND linear W diverges from it, on the SAME frame. If the negative side ever
    # falls below the floor, the frame has gone degenerate and the positive side is
    # zero-evidence -- so this test fails, by design.
    z = _load(name)
    spp = z["spp"]
    t0s, nar, wl = _frames(z)
    W, AR = z[f"w_{method}"], z[f"ar_{method}"]
    i, div = _probe_frame(z, method)
    x, w = _frame_slice(spp, W, int(t0s[i]), nar, wl)

    a_sq = lpc_covar(x, nar, weights=w**2, dc_offset=True).a
    np.testing.assert_allclose(a_sq, AR[i], atol=POSITIVE_ATOL, rtol=0)  # positive

    a_lin = lpc_covar(x, nar, weights=w, dc_offset=True).a
    assert np.max(np.abs(a_lin - AR[i])) > NEGATIVE_FLOOR  # negative control
    # the frame is genuinely full-rank (not a rank-deficient false separation)
    assert int(np.count_nonzero(w[nar:])) >= 2 * nar + 2


class TestSyntheticDecomposition:
    """Synthetic known-value check (the second mechanism): the reference is the SOLE
    oracle for these methods, so a golden-master pass proves "matches the reference,"
    not "computes what we expect." This asserts the DECOMPOSITION on a constructed
    rgauss cycle -- which sample carries which weight, and that W^2 enters the normal
    equations as the GIF1 mechanism says -- via an independent route (the reference's
    own dm.*w / s.*w residual weighting, reproduced in numpy), NOT lpc_covar's
    internals and NOT the MATLAB golden. This is the check that would catch the
    reference or lpc_covar being wrong, which the golden master structurally cannot.
    """

    order = 4
    nsp = 60
    gci = np.array([30.0])  # single GCI, 1-based
    # Deterministic and NOT exactly fittable at order 4: four spectral components need
    # order >= 8, so the order-4 residual is nonzero (norm ~3.2). An exactly-fittable
    # signal (e.g. two sinusoids = order 4) would zero the residual and make W and W^2
    # agree -- the second GIF1 blinding mechanism -- so it is deliberately avoided.
    n = np.arange(1, nsp + 1)
    s = np.sin(0.7 * n) + 0.3 * np.sin(1.9 * n) + 0.5 * np.cos(0.31 * n) + 0.2 * np.sin(2.6 * n)
    w = rgauss_weight(gci, nsp, fs=16000.0)

    def test_weight_decomposition_hand_values(self) -> None:
        # Which sample carries which weight: rgauss w = 1 - 0.9*exp(-0.5*(n-30)^2/50).
        # At the GCI (n=30): 1 - 0.9 = 0.1. Five samples off: 1 - 0.9*exp(-0.5*25/50).
        assert self.w[29] == pytest.approx(0.1, abs=1e-12)  # n=30 (index 29)
        off5 = 1.0 - 0.9 * np.exp(-0.5 * 25.0 / 50.0)
        assert self.w[24] == pytest.approx(off5, abs=1e-12)  # n=25
        assert self.w[34] == pytest.approx(off5, abs=1e-12)  # n=35 (symmetric)

    def test_w_squared_is_the_normal_equation_weighting(self) -> None:
        # The GIF1 mechanism on known values, decomposed: the reference weights the
        # RESIDUAL by w (dm.*w, s.*w), so the normal-equation matrix carries w^2.
        past = np.column_stack(
            [self.s[self.order - k : self.nsp - k] for k in range(1, self.order + 1)]
        )
        wp = self.w[self.order :]
        # reference mechanism: weight the design rows and target by w, then plain LS
        dm = wp[:, None] * past
        # the normal matrix of that mechanism IS the w^2-weighted normal matrix
        m_mechanism = dm.T @ dm
        m_w2 = past.T @ (wp[:, None] ** 2 * past)
        m_w = past.T @ (wp[:, None] * past)
        np.testing.assert_allclose(m_mechanism, m_w2, atol=1e-12)  # w-on-residual == w^2 normal
        assert np.max(np.abs(m_w2 - m_w)) > 1e-3  # w^2 genuinely differs from w

    def test_lpc_covar_w_squared_reproduces_reference_mechanism(self) -> None:
        # Independent route (no lpc_covar internals, no MATLAB): solve the reference's
        # own residual-weighted LS by hand, and show lpc_covar(weights=W^2) reproduces
        # it -- while lpc_covar(weights=W) (linear, wrong) does not.
        past = np.column_stack(
            [self.s[self.order - k : self.nsp - k] for k in range(1, self.order + 1)]
        )
        target = self.s[self.order :]
        wp = self.w[self.order :]
        coef, *_ = np.linalg.lstsq(wp[:, None] * past, -(wp * target), rcond=None)
        a_mechanism = np.concatenate(([1.0], coef))

        a_w2 = lpc_covar(self.s, order=self.order, weights=self.w**2).a
        np.testing.assert_allclose(a_w2, a_mechanism, atol=1e-12)  # positive

        a_w = lpc_covar(self.s, order=self.order, weights=self.w).a
        assert np.max(np.abs(a_w - a_mechanism)) > 1e-3  # negative control
