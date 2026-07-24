"""Shared per-cycle prep: build every `CyclePrep` once.

The signal feature groups (flow, timing, spectral) all work over the same per-cycle
segments, and several of them re-derived the same intermediates -- the flow segment
``useg = u[nn-1]/fs``, the period ``T``, and (for timing) the DC-shifted segment and
the open-phase detection ``O1``. This module computes all of that a single time so
the ``useg``/``uuseg`` extraction, the one DC-shift, and ``O1`` cannot drift between
groups, and so the seam has ``O1`` available to mask the degenerate cycles.

Reference: the reference feature-extraction pipeline (the per-cycle loop); reimplemented.
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round
from voicekit.features.config import FeaturesConfig
from voicekit.features.framework import CyclePrep, iter_cycle_segments
from voicekit.features.timing import open_close_timings


def prepare_cycles(
    u: npt.NDArray[np.float64],
    uu: npt.NDArray[np.float64],
    gci: npt.NDArray[np.int64],
    fs: float,
    config: FeaturesConfig | None = None,
) -> Sequence[CyclePrep]:
    """Build the `CyclePrep` for each of the ``len(gci)+1`` reference intervals.

    ``u`` is the glottal flow, ``uu`` its derivative, ``gci`` the 0-based closures.
    Each prep carries the unshifted ``useg``/``uuseg``, the single DC-shifted
    ``useg_shifted`` (derived here from the stored ``useg`` -- one shift site), and the
    open/quasi-open indices ``o1/o2/c1/c2`` from `open_close_timings` (computed once
    here, read by both timing and the seam's O1==0 mask).
    """
    cfg = config if config is not None else FeaturesConfig()
    u = np.asarray(u, dtype=np.float64)
    uu = np.asarray(uu, dtype=np.float64)

    preps: list[CyclePrep] = []
    for a, b, nn in iter_cycle_segments(gci, u.size):
        idx = nn - 1  # 1-based nn -> 0-based signal index
        useg = u[idx] / fs
        uuseg = uu[idx]
        period = nn.size - 2  # the framework T (V1 convention)

        # Single DC-shift site: shifted derives from the stored useg, so unshifted and
        # shifted provably share one origin. Subtract the [10%, 30%]-window mean (the
        # presumed closed phase; first 0.1 cut to stay clear of the GCI).
        lo = int(matlab_round(0.1 * period))
        hi = int(matlab_round(0.3 * period))
        useg_shifted = useg - useg[lo - 1 : hi].mean()

        o1, o2, c1, c2 = open_close_timings(
            useg_shifted, cfg.open_threshold, cfg.quasi_open_level, cfg.medfilt_window
        )
        preps.append(
            CyclePrep(
                a=a,
                b=b,
                nn=nn,
                period=period,
                useg=useg,
                uuseg=uuseg,
                useg_shifted=useg_shifted,
                o1=o1,
                o2=o2,
                c1=c1,
                c2=c2,
            )
        )
    return preps
