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

The reference additionally zeroes all three when no open phase is found
(``O1==0``); that couples them to the timing machinery and is applied at
orchestration once the timing group provides ``O1`` (see REFERENCE_NOTES.md
"Coverage gaps" C4). The fixtures never take that branch, so the plain formulas
reproduce them exactly here.

Reference: ``vsaTools/extractVoiceFeatures.m``; reimplemented, not ported.
"""

import numpy as np
import numpy.typing as npt

from voicekit.features.config import FeaturesConfig
from voicekit.features.framework import iter_cycle_segments

_MFDR_UNIT_SCALE = 1000.0  # cm^3/s^2 -> l/s^2


def flow_statistics(
    u: npt.NDArray[np.float64],
    uu: npt.NDArray[np.float64],
    gci: npt.NDArray[np.int64],
    fs: float,
    config: FeaturesConfig | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Raw per-interval ``(mfdr, pa, naq)`` over the ``len(gci)+1`` intervals.

    ``u`` is the glottal flow, ``uu`` its derivative; ``gci`` are 0-based sample
    indices (the `GciResult` convention). Returns arrays of length ``len(gci)+1``
    (the plain formulas -- the
    ``O1==0`` zeroing is applied downstream).
    """
    del config  # no tunable knobs for these extrema; signature kept for uniformity
    u = np.asarray(u, dtype=np.float64)
    uu = np.asarray(uu, dtype=np.float64)

    segments = list(iter_cycle_segments(gci, u.size))
    mfdr = np.zeros(len(segments))
    pa = np.zeros(len(segments))
    naq = np.zeros(len(segments))
    for ig, (_a, _b, nn) in enumerate(segments):
        idx = nn - 1  # 1-based nn -> 0-based signal index
        useg = u[idx] / fs
        uuseg = uu[idx]
        dpeak = -uuseg.min()
        fac = useg.max() - useg.min()
        t_time = (nn.size - 2) / fs
        mfdr[ig] = dpeak / _MFDR_UNIT_SCALE
        pa[ig] = fac
        with np.errstate(divide="ignore", invalid="ignore"):
            naq[ig] = fac / (dpeak * t_time)
    return mfdr, pa, naq
