"""Tests for the LPC solvers."""

from pathlib import Path

import numpy as np
import pytest
import scipy.linalg
import scipy.signal

from voicekit.lpc import levinson, lpc_auto, lpc_covar

# A stable AR(4) system used as ground truth throughout: two resonances,
# poles well inside the unit circle.
TRUE_A = np.poly(
    [
        0.95 * np.exp(1j * 0.3),
        0.95 * np.exp(-1j * 0.3),
        0.9 * np.exp(1j * 1.2),
        0.9 * np.exp(-1j * 1.2),
    ]
).real


def ar_process(a: np.ndarray, n: int, seed: int = 0) -> np.ndarray:
    """White noise filtered through the all-pole system 1/A(z)."""
    rng = np.random.default_rng(seed)
    x = scipy.signal.lfilter([1.0], a, rng.standard_normal(n + 1000))
    return np.asarray(x[1000:])  # discard transient


class TestLevinson:
    def test_matches_direct_toeplitz_solve(self) -> None:
        # Autocorrelation of a real signal guarantees a valid Toeplitz system
        x = ar_process(TRUE_A, 2000)
        r = np.array([x[: len(x) - lag] @ x[lag:] for lag in range(6)])
        a, e, k = levinson(r, 5)
        direct = scipy.linalg.solve_toeplitz((r[:5], r[:5]), -r[1:6])
        np.testing.assert_allclose(a[1:], direct, rtol=1e-8)
        assert e > 0
        assert np.all(np.abs(k) < 1)

    def test_zero_input(self) -> None:
        a, e, k = levinson(np.zeros(5), 4)
        np.testing.assert_array_equal(a, [1, 0, 0, 0, 0])
        assert e == 0.0

    def test_rejects_short_r(self) -> None:
        with pytest.raises(ValueError, match="lags"):
            levinson(np.ones(3), 4)


class TestLpcAuto:
    def test_recovers_ar_coefficients(self) -> None:
        x = ar_process(TRUE_A, 50_000)
        result = lpc_auto(x, order=4, window=None)
        np.testing.assert_allclose(result.a, TRUE_A, atol=0.02)

    def test_stability_guaranteed(self) -> None:
        # Even on arbitrary non-AR input the filter must be minimum phase
        rng = np.random.default_rng(7)
        for _ in range(20):
            x = rng.standard_normal(300) * rng.uniform(0.1, 10)
            result = lpc_auto(x, order=12)
            assert np.all(np.abs(np.roots(result.a)) < 1.0)
            assert result.reflection is not None
            assert np.all(np.abs(result.reflection) <= 1.0)

    def test_residual_energy_below_signal_energy(self) -> None:
        x = ar_process(TRUE_A, 2000)
        result = lpc_auto(x, order=4)
        windowed = x * scipy.signal.get_window("hamming", len(x), fftbins=False)
        assert 0 < result.error < windowed @ windowed

    def test_window_array_matches_window_name(self) -> None:
        x = ar_process(TRUE_A, 400)
        w = scipy.signal.get_window("hamming", 400, fftbins=False)
        np.testing.assert_allclose(lpc_auto(x, 4, window=w).a, lpc_auto(x, 4, window="hamming").a)

    def test_rejects_short_frame(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            lpc_auto(np.zeros(4), order=4)


class TestLpcCovar:
    def test_exact_recovery_from_impulse_response(self) -> None:
        # The impulse response of 1/A(z) is exactly predictable for n >= 1,
        # so covariance LPC recovers A to machine precision.
        h = scipy.signal.lfilter([1.0], TRUE_A, np.eye(1, 200, 0).ravel())
        result = lpc_covar(np.asarray(h), order=4)
        np.testing.assert_allclose(result.a, TRUE_A, atol=1e-10)
        assert result.error == pytest.approx(0.0, abs=1e-18)

    def test_recovers_ar_coefficients_on_noise_driven_data(self) -> None:
        x = ar_process(TRUE_A, 50_000)
        result = lpc_covar(x, order=4)
        np.testing.assert_allclose(result.a, TRUE_A, atol=0.02)

    def test_uniform_weights_match_default(self) -> None:
        x = ar_process(TRUE_A, 500)
        unweighted = lpc_covar(x, order=4)
        weighted = lpc_covar(x, order=4, weights=np.ones(len(x)))
        np.testing.assert_allclose(weighted.a, unweighted.a)
        assert weighted.error == pytest.approx(unweighted.error)

    def test_zero_weight_ignores_corrupted_region(self) -> None:
        # The scenario behind closed-phase/weighted GIF: zero-weighted
        # samples must not influence the fit at all.
        x = ar_process(TRUE_A, 2000)
        clean = lpc_covar(x, order=4)

        corrupted = x.copy()
        corrupted[800:900] += 50.0  # massive disturbance
        w = np.ones(len(x))
        w[796:904] = 0.0  # cover the disturbance plus `order` history samples
        masked = lpc_covar(corrupted, order=4, weights=w)
        biased = lpc_covar(corrupted, order=4)

        # Exactness: with the disturbance zero-weighted (including its use
        # as regressor history), corrupted and clean data give the same fit
        same_mask_on_clean = lpc_covar(x, order=4, weights=w)
        np.testing.assert_allclose(masked.a, same_mask_on_clean.a, atol=1e-9)
        # And that fit stays near the uniform-weight clean fit, while the
        # unmasked fit on corrupted data is pulled far away
        assert np.max(np.abs(masked.a - clean.a)) < 0.05
        assert np.max(np.abs(biased.a - clean.a)) > 0.1

    def test_scaling_weights_leaves_coefficients_unchanged(self) -> None:
        x = ar_process(TRUE_A, 500)
        w = np.ones(len(x))
        a1 = lpc_covar(x, order=4, weights=w).a
        a2 = lpc_covar(x, order=4, weights=3.7 * w).a
        np.testing.assert_allclose(a1, a2, rtol=1e-10)

    def test_rejects_negative_weights(self) -> None:
        with pytest.raises(ValueError, match="nonnegative"):
            lpc_covar(np.zeros(100), order=4, weights=-np.ones(100))

    def test_rejects_wrong_length_weights(self) -> None:
        with pytest.raises(ValueError, match="length"):
            lpc_covar(np.zeros(100), order=4, weights=np.ones(50))

    def test_signal_energy_equals_target_sum_of_squares(self) -> None:
        # signal_energy is the energy of exactly the samples the residual is
        # measured over (x[order:]), so a caller (VUV Es/Ep) gets consistent
        # signal and residual energy from one call.
        x = ar_process(TRUE_A, 500)
        result = lpc_covar(x, order=4)
        assert result.signal_energy == float(x[4:] @ x[4:])

    def test_signal_energy_is_unweighted(self) -> None:
        # v_lpccovar's signal-energy column is the plain window energy; weighting
        # affects the residual/error, not the signal energy.
        x = ar_process(TRUE_A, 500)
        w = np.ones(len(x))
        w[100:200] = 0.3
        assert lpc_covar(x, order=4, weights=w).signal_energy == pytest.approx(
            lpc_covar(x, order=4).signal_energy
        )

    def test_lpc_auto_leaves_signal_energy_none(self) -> None:
        # Additive and backward-compatible: only the covariance path sets it.
        assert lpc_auto(ar_process(TRUE_A, 500), order=4).signal_energy is None

    def test_dc_offset_recovers_ar_coefficients_despite_dc(self) -> None:
        # RECOVERY (that the DC path computes the RIGHT coefficients, which
        # invariance alone would not catch -- a zeros-returning solver is
        # DC-invariant too). A well-conditioned AR system plus a large DC:
        # dc_offset=True recovers the true coefficients to the same bar as the
        # noise-driven recovery test (atol 0.02); plain covariance LPC FAILS that
        # same bar -- visibly pulled off by the DC (dc dev ~0.01, plain dev ~0.13).
        a_true = np.poly([0.6, -0.5, 0.4, -0.3]).real
        x = ar_process(a_true, 8000) + 500.0
        np.testing.assert_allclose(lpc_covar(x, 4, dc_offset=True).a, a_true, atol=0.02)
        assert np.max(np.abs(lpc_covar(x, 4).a - a_true)) > 0.02  # plain fails the same bar

    def test_dc_offset_makes_ar_invariant_to_added_constant(self) -> None:
        # INVARIANCE (that the DC path ignores a DC level), the complementary
        # property recovery does not isolate: the DC-offset AR is unchanged by an
        # added constant, exactly (BLAS-eps).
        x = ar_process(TRUE_A, 5000)
        np.testing.assert_allclose(
            lpc_covar(x, 4, dc_offset=True).a, lpc_covar(x + 100.0, 4, dc_offset=True).a, atol=1e-9
        )

    def test_dc_offset_default_is_bit_identical(self) -> None:
        # Additive and default-off: the augmentation is skipped and the result is
        # bit-for-bit what it was before dc_offset existed.
        x = ar_process(TRUE_A, 500)
        r0 = lpc_covar(x, 4)
        rf = lpc_covar(x, 4, dc_offset=False)
        np.testing.assert_array_equal(r0.a, rf.a)
        assert r0.error == rf.error
        assert r0.signal_energy == rf.signal_energy

    def test_signal_energy_invariant_under_dc_offset(self) -> None:
        # signal_energy is the window energy (v_lpccovar e(:,2)); the DC option
        # changes ar/error, never the signal energy.
        x = ar_process(TRUE_A, 500) + 3.0
        assert lpc_covar(x, 4, dc_offset=True).signal_energy == lpc_covar(x, 4).signal_energy

    def test_dc_offset_ar_invariant_to_dc_column_position(self) -> None:
        # We append the ones column and slice coef[:order]; the reference prepends
        # and slices aa(2:p+1). Least-squares is invariant to design-column order,
        # so the AR coefficients agree -- a claim between our formulation and the
        # reference's that a later slicing change would silently break.
        order = 4
        x = ar_process(TRUE_A, 500) + 2.0
        ours = lpc_covar(x, order, dc_offset=True).a  # ones appended
        past = np.column_stack([x[order - k : len(x) - k] for k in range(1, order + 1)])
        target = x[order:]
        prepended = np.column_stack([np.ones(len(target)), past])  # ones prepended
        aa, *_ = np.linalg.lstsq(prepended, target, rcond=None)  # reference solves dm\sc
        ref_ar = np.concatenate(([1.0], -aa[1:]))  # AR = [1, -aa(2:p+1)]
        # Exact in infinite precision; the tiny residual is column-order BLAS rounding.
        np.testing.assert_allclose(ours, ref_ar, atol=1e-10)

    def test_rejects_short_frame(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            lpc_covar(np.zeros(8), order=4)


class TestWeightedCovarianceConvention:
    """Golden-master pin of the W-vs-W^2 weighting convention against v_lpccovar.

    The reference VOICEBOX ``v_lpccovar`` applies the weight as ``dm.*w`` /
    ``sc = s.*w``, minimising ``sum W^2 * resid^2`` (its header: "the error at
    each sample is weighted by W^2"). ``lpc_covar`` does ``sw = sqrt(w)``,
    minimising ``sum w * resid^2``. So reproducing the reference requires passing
    ``weights = W^2``, NOT ``W``. Every step-8 weighted-LP GIF method routes
    through this seam, and getting it wrong solves a different least-squares
    problem silently (no crash / NaN).

    The pre-step-8 weighted tests above could not disambiguate this: uniform
    weights (``test_uniform_weights_match_default``), a zero-mask
    (``test_zero_weight_ignores_corrupted_region``), and scaling
    (``test_scaling_weights_leaves_coefficients_unchanged``) are ALL invariant
    under both conventions -- scaling structurally so, since the solve is
    scale-invariant. This test closes that gap with a non-uniform, non-binary
    weight on a signal that is NOT exactly fittable at the probe order (an
    exactly-fittable signal -- see ``test_exact_recovery_from_impulse_response``
    -- makes both conventions agree via zero residual, a second way to blind the
    probe). Target captured by ``tests/golden/capture/capture_wcovar.py``.
    """

    GOLD = np.load(Path(__file__).resolve().parent / "golden" / "wcovar_weight_convention.npz")

    def _fixture(self) -> tuple[np.ndarray, np.ndarray, int]:
        return self.GOLD["s"], self.GOLD["W"], int(self.GOLD["order"])

    def test_w_squared_reproduces_reference_plain(self) -> None:
        s, w, order = self._fixture()
        got = lpc_covar(s, order=order, weights=w**2).a
        np.testing.assert_allclose(got, self.GOLD["ar_plain"], atol=1e-12)

    def test_w_squared_reproduces_reference_dc_offset(self) -> None:
        # The path the step-8 methods actually call: weightedlpc.m invokes the
        # three-output [ar,ee,dc]=lpccovar(sp,nar,T,w) form. Same W^2 convention.
        s, w, order = self._fixture()
        got = lpc_covar(s, order=order, weights=w**2, dc_offset=True).a
        np.testing.assert_allclose(got, self.GOLD["ar_dc"], atol=1e-12)

    def test_linear_w_does_not_reproduce_reference(self) -> None:
        # The disambiguation, asserted the other way: weights=W (the wrong
        # convention) is measurably off, so this fixture genuinely separates the
        # two. If this ever passes, the fixture has gone degenerate.
        s, w, order = self._fixture()
        wrong = lpc_covar(s, order=order, weights=w).a
        assert np.max(np.abs(wrong - self.GOLD["ar_plain"])) > 1e-3


class TestWeightedRankDeficiency:
    """Characterize the effective-support < order degeneracy (REFERENCE_NOTES GIF3).

    Distinct from C8 (the short-frame `nc < order` order-reduction). Here the
    frame is LONG (`nc >> order`) but a 0/1 weight leaves fewer nonzero samples
    than the order, so the weighted normal equations are rank-deficient on a long
    frame. `lpc_covar` returns the minimum-norm solution (numpy lstsq/SVD) --
    finite, no raise, no NaN. The reference `v_lpccovar` returns a *basic*
    solution (MATLAB backslash) instead, so the two diverge silently by ~0.12 on
    this fixture; that divergence is a FOUND fact recorded in GIF3, and the policy
    (guard/skip/reproduce) is deferred to the closed-phase implementation gate.
    This test does NOT assert a parity value -- it characterizes voicekit's
    current behaviour and pins that the fixture actually reaches the degeneracy.
    """

    order = 4
    N = 40
    n = np.arange(N)
    s = np.sin(0.7 * n) + 0.3 * np.sin(1.9 * n)
    w = np.zeros(N)
    w[[10, 20, 30]] = 1.0  # nonzero support = 3 < order = 4

    def test_fixture_reaches_the_degeneracy(self) -> None:
        # The three explicit checks: long frame, short support, rank-deficient.
        past = np.column_stack(
            [self.s[self.order - k : self.N - k] for k in range(1, self.order + 1)]
        )
        nc = past.shape[0]
        support = int(np.count_nonzero(self.w[self.order :]))
        rank = int(np.linalg.matrix_rank(np.sqrt(self.w[self.order :])[:, None] * past))
        assert nc > self.order  # (a) frame is long
        assert support < self.order  # (b) support is short
        assert rank < self.order  # (c) weighted design is rank-deficient

    def test_lpc_covar_returns_finite_min_norm_solution(self) -> None:
        # Current behaviour: no raise, no NaN, and the returned coefficients are
        # the minimum-2-norm least-squares solution (numpy lstsq). Documented, not
        # a decision -- see GIF3.
        res = lpc_covar(self.s, order=self.order, weights=self.w)
        assert np.all(np.isfinite(res.a))
        past = np.column_stack(
            [self.s[self.order - k : self.N - k] for k in range(1, self.order + 1)]
        )
        sw = np.sqrt(self.w[self.order :])
        coef_minnorm, *_ = np.linalg.lstsq(
            sw[:, None] * past, -sw * self.s[self.order :], rcond=None
        )
        np.testing.assert_allclose(res.a[1:], coef_minnorm, atol=1e-12)
