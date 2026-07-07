"""Per-cycle segmentation framework: the shared foundation for all features.

The reference brackets the GCIs as ``gciP = [1, gci, len(u)]`` and computes one
value per interval, giving ``len(gci)+1`` intervals: a left-edge non-cycle
(signal start to first closure), ``len(gci)-1`` genuine closure-to-closure
cycles, and a right-edge cycle (last closure to signal end). Every later feature
group is computed over these same intervals, so this framework -- the
segmentation, the period convention, the voicing test -- is validated first and
inherited by the rest.

Reference: ``vsaTools/extractVoiceFeatures.m`` (the per-cycle loop);
reimplemented from the source, not ported.
"""

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round
from voicekit.features.config import FeaturesConfig


def cycle_framework(
    gci: npt.NDArray[np.int64],
    n_samples: int,
    fs: float,
    config: FeaturesConfig | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Raw per-interval ``(f0, framek, vuv)`` over the ``len(gci)+1`` intervals.

    ``gci`` are 1-based sample indices (the reference frame); returns arrays of
    length ``len(gci)+1`` in the raw reference form (``framek`` 1-based, ``vuv``
    as 0/1). The period is ``T = len(nn)-2`` and ``f0 = fs/T`` -- the reference's
    convention (see REFERENCE_NOTES, "Feature observations": this makes ``f0``
    ``fs/(period-1)`` for interior cycles, not ``fs/period``).
    """
    cfg = config if config is not None else FeaturesConfig()
    gci = np.atleast_1d(np.asarray(gci)).astype(np.int64)
    gci_bracketed = np.concatenate([[1], gci, [n_samples]])  # 1-based interval bounds

    n_intervals = gci_bracketed.size - 1
    f0 = np.zeros(n_intervals)
    framek = np.zeros(n_intervals)
    vuv = np.zeros(n_intervals)

    t_lo = fs / cfg.voicing_f0_max  # fs/400
    t_hi = fs / cfg.voicing_f0_min  # fs/40
    for ig in range(n_intervals):
        a, b = int(gci_bracketed[ig]), int(gci_bracketed[ig + 1])
        framek[ig] = a + matlab_round((b - a) / 2)  # centre of the untrimmed interval
        nn = np.arange(a, b + 1)  # 1-based, inclusive (MATLAB a:b)
        nn = nn[(nn > 0) & (nn < n_samples)]  # trim to signal interior (drops sample n)
        period = nn.size - 2  # the reference's T = len(nn) - 2
        if t_lo < period < t_hi:
            vuv[ig] = 1.0
        with np.errstate(divide="ignore"):
            f0[ig] = fs / period
    return f0, framek, vuv
