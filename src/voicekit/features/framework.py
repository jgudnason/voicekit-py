"""Per-cycle segmentation framework: the shared foundation for all features.

The reference brackets the GCIs as ``gciP = [1, gci, len(u)]`` and computes one
value per interval, giving ``len(gci)+1`` intervals: a left-edge non-cycle
(signal start to first closure), ``len(gci)-1`` genuine closure-to-closure
cycles, and a right-edge cycle (last closure to signal end). Every later feature
group is computed over these same intervals, so this framework -- the
segmentation, the period convention, the voicing test -- is validated first and
inherited by the rest. `iter_cycle_segments` single-sources that segmentation so
the groups cannot drift on the trim/period conventions.

Reference: ``vsaTools/extractVoiceFeatures.m`` (the per-cycle loop);
reimplemented from the source, not ported.
"""

from collections.abc import Iterator

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round
from voicekit.features.config import FeaturesConfig


def iter_cycle_segments(
    gci: npt.NDArray[np.int64], n_samples: int
) -> Iterator[tuple[int, int, npt.NDArray[np.int64]]]:
    """Yield ``(a, b, nn)`` for each of the ``len(gci)+1`` reference intervals.

    ``gci`` are 0-based sample indices (the `GciResult` convention). This is the
    single place the reference's 1-based cycle frame is entered: the bracket is
    ``gciP = [1, gci+1, len(u)]``, so the ``+1`` here is the one conversion of the
    public 0-based indices into the reference frame. ``a``/``b`` are the untrimmed
    interval bounds (``gciP[ig]``/``gciP[ig+1]``); ``nn`` is the 1-based sample
    range trimmed to the signal interior (``0 < nn < n_samples``, dropping the
    final sample as the reference does). The period is ``T = nn.size - 2``.
    """
    gci = np.atleast_1d(np.asarray(gci)).astype(np.int64)
    bracketed = np.concatenate([[1], gci + 1, [n_samples]])  # gciP = [1, gci+1, len(u)]
    for ig in range(bracketed.size - 1):
        a, b = int(bracketed[ig]), int(bracketed[ig + 1])
        nn = np.arange(a, b + 1)  # 1-based inclusive (MATLAB a:b)
        nn = nn[(nn > 0) & (nn < n_samples)]
        yield a, b, nn


def cycle_framework(
    gci: npt.NDArray[np.int64],
    n_samples: int,
    fs: float,
    config: FeaturesConfig | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Raw per-interval ``(f0, framek, vuv)`` over the ``len(gci)+1`` intervals.

    ``gci`` are 0-based sample indices (the `GciResult` convention); returns arrays
    of length ``len(gci)+1`` in the raw reference form (``framek`` 1-based, ``vuv``
    as 0/1). The period is ``T = len(nn)-2`` and ``f0 = fs/T`` -- the reference's
    convention (see REFERENCE_NOTES, "Feature observations" V1: this makes ``f0``
    ``fs/(period-1)`` for interior cycles, not ``fs/period``).
    """
    cfg = config if config is not None else FeaturesConfig()
    segments = list(iter_cycle_segments(gci, n_samples))
    n_intervals = len(segments)
    f0 = np.zeros(n_intervals)
    framek = np.zeros(n_intervals)
    vuv = np.zeros(n_intervals)

    t_lo = fs / cfg.voicing_f0_max  # fs/400
    t_hi = fs / cfg.voicing_f0_min  # fs/40
    for ig, (a, b, nn) in enumerate(segments):
        framek[ig] = a + matlab_round((b - a) / 2)  # centre of the untrimmed interval
        period = nn.size - 2  # the reference's T = len(nn) - 2
        if t_lo < period < t_hi:
            vuv[ig] = 1.0
        with np.errstate(divide="ignore"):
            f0[ig] = fs / period
    return f0, framek, vuv
