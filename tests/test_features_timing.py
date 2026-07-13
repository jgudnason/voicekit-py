"""Tests for the open/closed timing kernel and its CQ/QOQ consumers.

Parity (the gate): cq/qoq reproduce the captured reference arrays, all three
fixtures, machine-epsilon. This is also the *transitive* proof of the timing
kernel, whose O1/O2/C1/C2 intermediates are not in the capture.

Synthetic threshold-certification (the flashlight, load-bearing here): the kernel
has no direct parity arbiter, so a constructed trapezoid with an analytic
5%-crossing certifies that the detector places O1/C1 at the boundary we *expect*,
not merely wherever 0.05 lands on the fixtures. The tolerance is the median
filter's real reach (a few samples), tight enough that a wrong threshold -- which
would land ~45 samples away, at the 50% crossing -- fails it. A pedestal-invariance
check certifies the DC-shift; a flat cycle exercises the O1==0 degenerate branch
that no fixture reaches (REFERENCE_NOTES.md C4).
"""

import warnings
from pathlib import Path

import numpy as np
import pytest

from voicekit.features import (
    extract_voice_features,
    open_close_timings,
    open_periods,
    prepare_cycles,
    timing_statistics,
)

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]

_MEDFILT_REACH = 3  # a 7-wide median filter can shift a single edge by <= floor(7/2)


def _trapezoid(peak: float, closed: int, ramp: int, plateau: int, tail: int) -> np.ndarray:
    """Flat-zero closed phase -> linear ramp -> plateau (the max) -> linear fall."""
    x = np.zeros(closed + ramp + plateau + ramp + tail)
    x[closed : closed + ramp] = peak * np.arange(ramp) / ramp
    x[closed + ramp : closed + ramp + plateau] = peak
    x[closed + ramp + plateau : closed + 2 * ramp + plateau] = peak * (1 - np.arange(ramp) / ramp)
    return x


# --- Parity (the gate) + transitive kernel proof -----------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_timing_matches_capture(name):
    """Raw cq/qoq reproduce the captured reference arrays (proves the kernel too)."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci = d["gci"].astype(np.int64) - 1  # 0-based (GciResult convention)
    cq, qoq = timing_statistics(prepare_cycles(d["feat_u"], d["udash"], gci, fs))

    np.testing.assert_allclose(cq, d["feat_cq"], rtol=1e-12, atol=1e-14)
    np.testing.assert_allclose(qoq, d["feat_qoq"], rtol=1e-12, atol=1e-14)


# --- Synthetic threshold-certification (the flashlight) ----------------------


def test_synthetic_open_boundary_at_five_percent_crossing():
    """The kernel locates O1/C1 at the analytic 5% crossings, within the filter's reach.

    On a trapezoid (baseline already 0, so the detector is tested in isolation) the
    flow crosses 5% of its peak at ``closed + 0.05*ramp`` going up and symmetrically
    coming down. The recovered O1/C1 must sit within the median filter's reach of
    those samples -- and far from the 50% crossing, so a wrong threshold fails.
    """
    peak, closed, ramp, plateau, tail = 1.0, 20, 100, 40, 20
    x = _trapezoid(peak, closed, ramp, plateau, tail)
    o1, o2, c1, c2 = open_close_timings(x, 0.05, 0.5, 7)

    # Rising mask turns on at the first sample past 5% of the ramp; the diff-index
    # convention places O one sample before, giving O1 ~ closed + ceil(0.05*ramp).
    up5 = closed + int(np.ceil(0.05 * ramp)) + 1  # 1-based, sample-before-rise
    dn5 = closed + ramp + plateau + int(np.floor(0.95 * ramp)) + 1
    assert abs(o1 - up5) <= _MEDFILT_REACH, (o1, up5)
    assert abs(c1 - dn5) <= _MEDFILT_REACH, (c1, dn5)

    # Discrimination: the 50% crossing is ~0.45*ramp away; a wrong threshold there
    # would fail the tight window above.
    up50 = closed + int(round(0.5 * ramp))
    assert abs(o1 - up50) > 10 * _MEDFILT_REACH

    # Quasi-open nests inside the open phase and sits near the 50% level.
    assert o1 <= o2 <= c2 <= c1
    assert abs((o2 - o1) - int(round(0.5 * ramp))) <= 2 * _MEDFILT_REACH


def test_synthetic_shift_makes_thresholding_pedestal_invariant():
    """The DC-shift certifies out: the same pulse on a pedestal yields the same cq/qoq.

    ``usegShift`` subtracts the mean over the cycle's [10%, 30%] window (the closed
    phase), so a constant offset on the whole cycle cancels before thresholding.
    Without the shift, a pedestal would move the 5%-of-peak crossing and change cq.
    """
    fs, peak, closed, ramp, plateau, tail = 16000.0, 1.0, 60, 120, 60, 60
    cycle = _trapezoid(peak, closed, ramp, plateau, tail)
    period = cycle.size
    u = np.tile(cycle, 4)
    gci = np.array([period, 2 * period, 3 * period], dtype=np.int64) - 1  # 0-based closures
    uu = np.zeros_like(u)  # timing ignores uuseg; prepare_cycles needs an array

    cq0, qoq0 = timing_statistics(prepare_cycles(u, uu, gci, fs))
    cq_ped, qoq_ped = timing_statistics(prepare_cycles(u + 5.0, uu, gci, fs))  # pedestal
    np.testing.assert_allclose(cq_ped, cq0)
    np.testing.assert_allclose(qoq_ped, qoq0)
    assert cq0[1] > 0  # interior cycle actually detected an open phase


def test_kernel_reports_no_open_phase_on_flat_input():
    """The detection kernel yields O1==0 on a cycle with no rising edge.

    No committed fixture reaches this (REFERENCE_NOTES.md C4); this checks the kernel
    directly. A flat cycle has no rising edge, so ``open_periods`` returns empty and
    ``open_close_timings`` yields O1==0. (Composed seam masking is covered separately.)
    """
    flat = np.ones(200)
    assert open_periods(flat, 0.05, 7)[0].size == 0
    assert open_close_timings(flat, 0.05, 0.5, 7) == (0, 0, 0, 0)


def test_timing_leaves_reference_zero_on_o1_zero_without_raising():
    """On an O1==0 cycle timing keeps cq=qoq=0 (the reference value) and does not raise.

    timing no longer *masks*; it guards qoq's 0/0 (which would raise) and leaves the
    cell at its 0.0 init -- the reference's degenerate value. The seam's O1==0 mask is a
    redundant safety net over this; the composed zeroing of all five is asserted in the
    extract-level C4 test.
    """
    fs, period = 16000.0, 200
    u = np.tile(np.ones(200), 4)  # flat cycles -> no open phase -> O1==0
    uu = np.zeros_like(u)
    gci = np.array([period, 2 * period, 3 * period], dtype=np.int64) - 1  # 0-based
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # a 0/0 would surface as a RuntimeWarning
        cq, qoq = timing_statistics(prepare_cycles(u, uu, gci, fs))
    assert cq[1] == 0.0 and qoq[1] == 0.0  # reference value, from init (not a mask)


# --- Shape ------------------------------------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_extract_fills_timing_fields(name):
    """extract_voice_features populates cq/qoq (this group's fields)."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    gci0 = d["gci"].astype(np.int64) - 1  # 0-based
    vf = extract_voice_features(d["feat_u"], d["udash"], fs, gci0)

    np.testing.assert_allclose(vf.cq, d["feat_cq"][1:])  # left-edge dropped
    np.testing.assert_allclose(vf.qoq, d["feat_qoq"][1:])
