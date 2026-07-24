"""Tests for the path-dependent DP cost kernels.

Golden master (sole arbiter): both kernels evaluated at the captured optimal
path's (r,q,p) triples -- extracted from gci_dp -- against vus_dp_mycost cols
1-2, all three fixtures, machine-epsilon. The captured udash and gci_dp are fed
as data; the kernels are not wired to the live modules.

The pitch kernel owns only the non-spurt rows: talkspurt-start transitions carry
dy_cspurt (= -0.45) instead, which the DP's spurt logic (sub-piece 2) supplies.
That separation is asserted as SET EQUALITY -- {rows the kernel misses} == {cspurt
rows} -- so a kernel bug that also perturbed a non-spurt row cannot hide inside a
plain exclusion.

Orthogonal (fixture- and library-independent): waveform self- and anti-correlation
(identical / negated windows -> Pearson +-1 -> +-0.5*(nx2-1)/(nx2-2)); pitch at
equal periods -> exactly -0.5, and a hand-computed unequal case. No library
cross-check (DYPSA-specific).
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga import dp_kernels as dk

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]
CSPURT = -0.45  # dy_cspurt: the talkspurt-start pitch cost


# --- 1. Golden master (the arbiter) ----------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_waveform_similarity_matches_capture(name):
    """q_cas reproduces mycost[:,0] at every path transition (k>=1)."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci = d["gci_dp"].astype(np.int64)
    mycost = d["vus_dp_mycost"]
    # Transition into gci[k] is from gci[k-1]; k=0 has no predecessor.
    cost = dk.waveform_similarity(d["udash"], gci[1:], gci[:-1], fs)
    np.testing.assert_allclose(cost, mycost[1:, 0], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_pitch_deviation_matches_capture_and_spurt_separation(name):
    """f_cp reproduces mycost[:,1] on exactly the non-spurt rows (set equality)."""
    d = np.load(GOLDEN / f"{name}.npz")
    gci = d["gci_dp"].astype(np.int64)
    ref = d["vus_dp_mycost"][2:, 1]  # rows k>=2 have both a current and previous period
    current = gci[2:] - gci[1:-1]
    previous = gci[1:-1] - gci[:-2]
    kernel = dk.pitch_deviation(current, previous)

    matches = np.isclose(kernel, ref, rtol=1e-10, atol=1e-12)
    is_spurt = np.isclose(ref, CSPURT)
    # The kernel must miss exactly the cspurt rows -- no more, no fewer.
    assert set(np.where(~matches)[0]) == set(np.where(is_spurt)[0])


def test_pitch_deviation_k2_anomaly_is_discriminating():
    """The k=2 row (odd first-cycle period) is a non -0.5 value the kernel must hit.

    On vowel_f0100_16k the third selected GCI closes an 81-sample cycle inside a
    160-sample train, so mycost[2,1] is +0.4525, not the steady-state -0.5. This
    is the discriminating case: an implementation stuck at -0.5 would pass the
    steady rows but fail here.
    """
    d = np.load(GOLDEN / "vowel_f0100_16k.npz")
    gci = d["gci_dp"].astype(np.int64)
    ref = float(d["vus_dp_mycost"][2, 1])
    assert not np.isclose(ref, -0.5)  # genuinely anomalous
    kernel = dk.pitch_deviation(gci[2] - gci[1], gci[1] - gci[0])
    np.testing.assert_allclose(kernel, ref, rtol=1e-10, atol=1e-12)


# --- 2. Orthogonal, hand-built checks --------------------------------------


def _place(signal, position, pattern):
    """Write `pattern` into `signal` at the waveform window around `position`."""
    fs = 16000.0
    nxc = int(np.ceil(0.01 * fs))
    half = nxc // 2
    wavix = np.arange(-half, half + 2)
    signal[(position - 1) + wavix] = pattern
    return wavix.size


def test_waveform_self_and_anti_correlation():
    """Identical windows -> Pearson 1; negated windows -> Pearson -1.

    The bias factor makes the costs -0.5*(nx2-1)/(nx2-2) and +0.5*(nx2-1)/(nx2-2)
    respectively -- the kernel's known extreme values, independent of the fixture.
    """
    fs = 16000.0
    rng = np.random.default_rng(0)
    n = 3000
    r, q = 1000, 300  # windows [919,1080] and [219,380] do not overlap
    nxc = int(np.ceil(0.01 * fs))
    pattern = rng.standard_normal(nxc + 2)  # nonzero variance
    nx2 = nxc + 2
    bias = -0.5 * (nx2 - 1) / (nx2 - 2)

    same = np.zeros(n)
    _place(same, r, pattern)
    _place(same, q, pattern)
    np.testing.assert_allclose(dk.waveform_similarity(same, [r], [q], fs), [bias], atol=1e-12)

    anti = np.zeros(n)
    _place(anti, r, pattern)
    _place(anti, q, -pattern)
    np.testing.assert_allclose(dk.waveform_similarity(anti, [r], [q], fs), [-bias], atol=1e-12)


def test_pitch_equal_periods_is_minus_half():
    """Equal current and previous periods give f_nx=0, so the cost is exactly -0.5."""
    np.testing.assert_allclose(dk.pitch_deviation(160, 160), -0.5, atol=1e-15)


def test_pitch_unequal_periods_hand_computed():
    """A hand-computed unequal case pins the f_nx formula and the scale."""
    a, b = 160.0, 80.0
    f_nx = 2 - 2 * (a + b) / ((a + b) + abs(a - b))  # = 0.5
    expected = 0.5 - np.exp(-12.5 * f_nx**2)
    np.testing.assert_allclose(dk.pitch_deviation(a, b), expected, atol=1e-15)
