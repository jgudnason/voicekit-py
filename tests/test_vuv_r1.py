"""Synthetic known-value tests for the decision-layer r1 statistic.

No golden master here by design: r1 is define-the-target (no MATLAB oracle
exists for the decision layer), so these tests are the load-bearing mechanism.
Expected values come from docs/vuv_r1_null.md, written before these tests --
derive -> predict -> check.
"""

import numpy as np
import pytest

from voicekit.vuv.decision import r1
from voicekit.vuv.features import frame_features_at

N = 512  # VoicingGrid.frame_len at 16 kHz


def test_constant_frame_is_exactly_one():
    # All-equal samples: x == y, so <x,y>/(|x||y|) = 1 exactly (integer-valued
    # float sums, exact in IEEE) -- and the DC hazard (VUV12) in its purest form.
    s = np.ones(N + 1)
    assert r1(s, 1, N) == 1.0


def test_alternating_frame_is_exactly_minus_one():
    # s[n] = (-1)^n: y = -x exactly, so r1 = -1 exactly.
    s = (-1.0) ** np.arange(N + 1)
    assert r1(s, 1, N) == -1.0


def test_bounded_by_cauchy_schwarz_even_with_huge_boundary_sample():
    # The construction that blows up the broadcast C1: an enormous s0 in front
    # of a small-noise frame. r1 must stay in [-1, 1] (exact inner-product
    # normalization); the feature layer's C1 exceeds 1 on the same input,
    # which is the structural difference between Eq. (3) and the reproduced
    # broadcast (VUV7/VUV8) -- asserted against the real shipped feature path.
    rng = np.random.default_rng(7)
    s = rng.standard_normal(N + 32) * 0.01
    s[31] = 1e6  # boundary sample for the frame starting at 32
    val = r1(s, 32, N)
    assert -1.0 <= val <= 1.0
    # Unbounded in MAGNITUDE (the sign follows frame[0]*s0): |C1| >> 1 while
    # r1 stays inside [-1, 1] on the identical input.
    c1_broadcast = frame_features_at(s, 32, N, 16)[2]
    assert abs(c1_broadcast) > 1.0


def test_bounds_hold_on_random_signals():
    rng = np.random.default_rng(11)
    s = rng.standard_normal(20 * N)
    vals = [r1(s, k * N + 1, N) for k in range(19)]
    assert all(-1.0 <= v <= 1.0 for v in vals)


def test_white_null_mean_zero_std_inverse_sqrt_n():
    # docs/vuv_r1_null.md: E[r1] = 0 exactly, std ~ 1/sqrt(N) = 0.0442 @ N=512.
    # M = 2000 disjoint frames -> the std estimate itself has ~1/sqrt(2M) = 1.6%
    # relative sampling error; the 6% assertion window is ~4x that, a named
    # tolerance, not a fit.
    rng = np.random.default_rng(3)
    m = 2000
    s = rng.standard_normal(m * N + 1)
    vals = np.array([r1(s, k * N + 1, N) for k in range(m)])
    predicted_std = 1.0 / np.sqrt(N)
    assert abs(vals.mean()) < 4.0 * predicted_std / np.sqrt(m)
    assert 0.94 * predicted_std < vals.std() < 1.06 * predicted_std


def test_coloured_noise_mean_is_rho_not_two_rho():
    # docs/vuv_r1_null.md: E[r1] ~ rho for noise with lag-1 correlation rho --
    # the coloured-noise floor as a bias. AR(1) with a = 0.6 has rho = 0.6
    # exactly. Tolerance 0.02 covers the O(1/N) small-sample bias of sample
    # autocorrelation (~(1+4*rho)/N = 0.007) plus sampling error of the mean.
    rng = np.random.default_rng(5)
    m = 500
    e = rng.standard_normal(m * N + 4 * N)
    ar = np.empty_like(e)
    ar[0] = e[0]
    for i in range(1, len(e)):
        ar[i] = 0.6 * ar[i - 1] + e[i]
    ar = ar[4 * N :]  # drop the burn-in
    vals = np.array([r1(ar, k * N + 1, N) for k in range(m - 1)])
    assert abs(vals.mean() - 0.6) < 0.02


def test_zero_frame_is_nan():
    # 0/0: the statistic reports NaN; the label mapping is the rule's
    # finiteness predicate (VUV1 J1), not the statistic's.
    s = np.zeros(N + 1)
    assert np.isnan(r1(s, 1, N))


def test_start_zero_is_refused():
    # No boundary sample exists at start=0; silent wrap to s[-1] (the signal
    # tail) is the failure the guard exists to prevent.
    s = np.ones(N + 1)
    with pytest.raises(ValueError):
        r1(s, 0, N)
