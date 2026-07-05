"""Tests for frame-based LPC and time-varying inverse filtering."""

import numpy as np
import pytest
import scipy.signal

from voicekit.lpc import inverse_filter_frames, lpc_auto, lpc_auto_frames


@pytest.fixture
def x() -> np.ndarray:
    rng = np.random.default_rng(3)
    return np.asarray(scipy.signal.lfilter([1.0], [1.0, -0.8], rng.standard_normal(2000)))


class TestLpcAutoFrames:
    def test_matches_per_frame_lpc(self, x: np.ndarray) -> None:
        coeffs, starts = lpc_auto_frames(x, order=4, frame_len=320, hop=160)
        assert coeffs.shape == ((2000 - 320) // 160 + 1, 5)
        np.testing.assert_array_equal(starts, np.arange(len(coeffs)) * 160)
        for i, s in enumerate(starts):
            expected = lpc_auto(x[s : s + 320], order=4).a
            np.testing.assert_allclose(coeffs[i], expected)

    def test_short_signal_analyzed_as_single_frame(self, x: np.ndarray) -> None:
        coeffs, starts = lpc_auto_frames(x[:100], order=4, frame_len=320, hop=160)
        assert coeffs.shape == (1, 5)
        np.testing.assert_array_equal(starts, [0])
        np.testing.assert_allclose(coeffs[0], lpc_auto(x[:100], order=4).a)


class TestInverseFilterFrames:
    def test_constant_coefficients_equal_global_filtering(self, x: np.ndarray) -> None:
        # A(z) is FIR, so with warm-up the piecewise result is exact
        a = lpc_auto(x, order=6).a
        coeffs = np.tile(a, (12, 1))
        starts = np.arange(12, dtype=np.int64) * 160
        piecewise = inverse_filter_frames(x, coeffs, starts)
        globally = scipy.signal.lfilter(a, [1.0], x)
        np.testing.assert_allclose(piecewise, globally, atol=1e-12)

    def test_segments_use_their_own_coefficients(self, x: np.ndarray) -> None:
        a1 = np.array([1.0, -0.5, 0.0])
        a2 = np.array([1.0, 0.0, 0.25])
        coeffs = np.stack([a1, a2])
        starts = np.array([0, 1000], dtype=np.int64)
        y = inverse_filter_frames(x, coeffs, starts)
        np.testing.assert_allclose(y[:1000], scipy.signal.lfilter(a1, [1.0], x)[:1000])
        np.testing.assert_allclose(y[1000:], scipy.signal.lfilter(a2, [1.0], x)[1000:])

    def test_rejects_mismatched_inputs(self, x: np.ndarray) -> None:
        coeffs = np.ones((3, 5))
        with pytest.raises(ValueError, match="frame starts"):
            inverse_filter_frames(x, coeffs, np.array([0, 100], dtype=np.int64))
        with pytest.raises(ValueError, match="increasing"):
            inverse_filter_frames(x, coeffs, np.array([0, 200, 100], dtype=np.int64))
