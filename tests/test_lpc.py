"""Tests for the LPC solvers."""

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

    def test_rejects_short_frame(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            lpc_covar(np.zeros(8), order=4)
