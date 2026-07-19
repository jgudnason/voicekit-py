"""Flow-statistic voice features: MFDR, PA, NAQ.

These are per-cycle extrema of the glottal flow and its derivative -- no
open/closed timing machinery, so they are independent of the timing group. Over
each cycle segment (``useg = u(nn)/fs``, ``uuseg = uu(nn)``):

    dpeak = -min(uuseg)               maximum flow declination rate
    fac   = max(useg) - min(useg)     peak-to-peak flow
    mfdr  = dpeak / 1000              (cm^3/s^2 -> l/s^2 unit conversion)
    pa    = fac                       pulse amplitude (carries the useg 1/fs scaling)
    naq   = fac / (dpeak * Ttime)     Alku's NAQ; the 1/fs on fac and Ttime cancel

NAQ matches Alku's ``f_ac/(d_peak*T)`` exactly except that ``Ttime`` uses the
framework period ``T = len(nn)-2``, so NAQ inherits observation V1's
``period-1`` convention (see REFERENCE_NOTES) -- the same cause, not a new one.

On ``O1==0`` cycles the reference does not compute these -- its degenerate branch
assigns ``0`` to all five timing/flow features (see REFERENCE_NOTES.md "Coverage
gaps" C4). So this group gates on the shared ``O1`` too: an ``o1==0`` cycle keeps its
``0.0`` init (the reference value, correct even if the seam's redundant mask misses),
and its division is skipped. The fixtures never take that branch, so the plain
formulas reproduce them exactly.

Reference: the reference feature-extraction pipeline; reimplemented, not ported.
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from voicekit.features.framework import CyclePrep

_MFDR_UNIT_SCALE = 1000.0  # cm^3/s^2 -> l/s^2


def flow_statistics(
    preps: Sequence[CyclePrep], fs: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Raw per-cycle ``(mfdr, pa, naq)`` over the prepared cycles.

    Reads the UNSHIFTED ``useg``/``uuseg`` from each `CyclePrep`. On ``o1==0`` cycles
    the reference assigns ``0`` (it does not compute these), so those cells are left at
    their ``0.0`` init. ``naq``'s ``fac/(dpeak*t)`` keeps its ``errstate`` IEEE shim
    (``dpeak==0`` -> MATLAB ``inf``/``nan``, measure-zero), reached only on ``o1!=0``.
    """
    mfdr = np.zeros(len(preps))
    pa = np.zeros(len(preps))
    naq = np.zeros(len(preps))
    for ig, p in enumerate(preps):
        if p.o1 == 0:
            continue  # no open phase: reference assigns 0; leave init (see C4)
        dpeak = -p.uuseg.min()
        fac = p.useg.max() - p.useg.min()
        t_time = p.period / fs
        mfdr[ig] = dpeak / _MFDR_UNIT_SCALE
        pa[ig] = fac
        with np.errstate(divide="ignore", invalid="ignore"):
            naq[ig] = fac / (dpeak * t_time)
    return mfdr, pa, naq
