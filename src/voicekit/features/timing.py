"""Open/closed timing machinery: the shared kernel for CQ and QOQ.

The one substantial shared component of the feature fan -- two consumers
(``cq``, ``qoq``) build on the same level-crossing detection, so it is validated
as an isolated kernel before either feature is layered on it. Its O1/O2/C1/C2
intermediates are *not* in the golden capture, so it has no direct parity
arbiter: correctness rests on the synthetic threshold-certification (does the
detector place the boundary where the flow analytically crosses the level?) plus
the transitive parity of the downstream cq/qoq it feeds.

Per cycle the reference DC-shifts the flow so the presumed closed phase sits near
zero, then runs two nested level-crossing detections on the shifted flow:

    usegShift = useg - mean(useg[0.1*T : 0.3*T])   DC-shift to the closed baseline
    (O1, C1)  = openPeriods(usegShift, opThres)     open phase, 5% of peak
    (O2, C2)  = openPeriods(usegShift[O1:C1], qoq)  quasi-open phase, 50% of the
                                                    peak *within* the open phase

``openPeriods`` thresholds at ``th*max(x)`` (a fraction of the peak, not
peak-to-peak), median-filters the 0/1 mask to de-glitch it, and reads the level
crossings off ``diff``: rising edges start open segments, the next falling edge
ends them. The longest segment wins. The quasi-open detection runs *within* the
open segment and its indices are re-shifted by ``+O1`` back into the cycle frame
(the nesting bridge). ``cq = O1/T``; ``qoq = (C2-O2)/O2``.

The DC-shift uses the mean of the flow over the cycle's [10%, 30%] window, not
the median: the reference tried ``useg - median(useg)`` (its line 88, annotated
"This way we get CQ aprox= 0.5 ??") and rejected it, so this convention is
deliberate. ``opThres``/``qoq_level``/``medfilt_window`` are the genuine tunable
knobs (they parameterize the detection) and are read from `FeaturesConfig`.

``qoq``'s denominator is the index ``O2`` rather than a duration -- reproduced,
not corrected; see REFERENCE_NOTES.md "Feature observations" V2. When no open
phase is detected (``O1==0``) the reference zeroes cq/qoq (and the flow group);
no fixture cycle triggers it -- see REFERENCE_NOTES.md "Coverage gaps" C4.

Reference: the reference feature-extraction pipeline (``openclosetimings`` /
``openPeriods``); reimplemented from the source, not ported.
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from scipy.signal import medfilt

from voicekit.features.framework import CyclePrep


def open_periods(
    x: npt.NDArray[np.float64], threshold: float, window: int
) -> tuple[npt.NDArray[np.int64], npt.NDArray[np.int64], npt.NDArray[np.int64]]:
    """Locate open segments where ``x`` exceeds ``threshold*max(x)``.

    Thresholds ``x`` at a fraction of its peak, median-filters the 0/1 mask
    (window ``window``) to de-glitch it, and reads level crossings off ``diff``:
    each rising edge (1-based index, the sample *before* the rise, per the
    reference's ``find(diff==1)`` convention) starts an open segment that ends at
    the next falling edge, or at the signal end if none follows. Returns the
    1-based ``(O, C, seg_len)`` arrays; all empty when no rising edge is found
    (the degenerate "no open phase" case the caller treats as ``O1==0``).
    """
    x = np.asarray(x, dtype=np.float64)
    mask = (x > threshold * x.max()).astype(np.float64)
    chsign = np.diff(medfilt(mask, window))
    pch = np.flatnonzero(chsign == 1) + 1  # 1-based rising edges (open starts)
    nch = np.flatnonzero(chsign == -1) + 1  # 1-based falling edges (open ends)
    if pch.size == 0:
        empty = np.empty(0, dtype=np.int64)
        return empty, empty, empty

    n = x.size
    o = np.empty(pch.size, dtype=np.int64)
    c = np.empty(pch.size, dtype=np.int64)
    seg_len = np.empty(pch.size, dtype=np.int64)
    for i, start in enumerate(pch):
        after = nch[nch > start]
        close = int(after[0]) if after.size else n  # no closing -> segment runs to end
        o[i] = start
        c[i] = close
        seg_len[i] = close - start
    return o, c, seg_len


def open_close_timings(
    x: npt.NDArray[np.float64],
    open_threshold: float,
    quasi_open_level: float,
    window: int,
) -> tuple[int, int, int, int]:
    """Nested open/quasi-open detection: return 1-based ``(O1, O2, C1, C2)``.

    ``(O1, C1)`` is the longest open segment at ``open_threshold`` (5% of peak);
    ``(O2, C2)`` is the longest quasi-open segment at ``quasi_open_level`` (50%)
    detected *within* ``x[O1:C1]`` and re-indexed by ``+O1`` back into the cycle
    frame. ``O1 == 0`` signals no open phase (caller zeroes the features); if an
    open phase exists but no quasi-open segment does, ``(O2, C2)`` collapses onto
    ``(O1, C1)``.
    """
    o1a, c1a, seg_len = open_periods(x, open_threshold, window)
    if o1a.size == 0:
        return 0, 0, 0, 0  # O1==0: no open phase found

    longest = int(np.argmax(seg_len))  # many segments possible -> take the longest
    o1, c1 = int(o1a[longest]), int(c1a[longest])

    # Quasi-open detection runs within the open segment x(O1:C1) (1-based inclusive).
    o2a, c2a, seg_len2 = open_periods(x[o1 - 1 : c1], quasi_open_level, window)
    if o2a.size == 0:
        return o1, o1, c1, c1  # no quasi-open segment -> collapse onto the open phase

    longest2 = int(np.argmax(seg_len2))
    o2 = int(o2a[longest2]) + o1  # +O1 re-indexes the sub-segment back to the cycle frame
    c2 = int(c2a[longest2]) + o1
    return o1, o2, c1, c2


def timing_statistics(
    preps: Sequence[CyclePrep],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Raw per-cycle ``(cq, qoq)`` over the prepared cycles.

    Reads ``o1/o2/c2`` and ``period`` from each `CyclePrep` -- ``O1`` (and the DC-shift
    behind it) is computed once in `prepare_cycles`, not here. ``cq = O1/T`` (closed
    quotient); ``qoq = (C2-O2)/O2`` (the ``O2`` denominator is the reference's, see
    REFERENCE_NOTES.md V2). On ``o1==0`` cycles the reference assigns ``0``; those cells
    are left at their ``0.0`` init (the parity value -- correct even if the seam's
    redundant mask misses), and the guard skips ``qoq``'s ``0/0`` division.
    """
    cq = np.zeros(len(preps))
    qoq = np.zeros(len(preps))
    for ig, p in enumerate(preps):
        if p.o1 == 0:
            continue  # no open phase: cq=qoq=0 (reference value), and skip qoq's 0/0
        cq[ig] = p.o1 / p.period
        qoq[ig] = (p.c2 - p.o2) / p.o2
    return cq, qoq
