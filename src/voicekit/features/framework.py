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
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round
from voicekit.features.config import FeaturesConfig


@dataclass(frozen=True)
class CyclePrep:
    """Per-cycle prep shared by the signal feature groups (flow, timing, spectral).

    Built once by `prepare_cycles` so the ``useg``/``uuseg`` extraction, the DC-shift,
    and ``O1`` are computed a single time and cannot drift between groups. The three
    segment arrays are kept **distinct on purpose**: ``pa`` (peak-to-peak) and the
    spectral FFT are shift-invariant, so collapsing them to one array would still pass
    the golden gate -- but the reference feeds *unshifted* flow to flow/spectral and
    *shifted* flow to timing, and the two must not silently merge.
    """

    a: int  # untrimmed 1-based bracket start (framek)
    b: int  # untrimmed 1-based bracket end (framek)
    nn: npt.NDArray[np.int64]  # 1-based trimmed sample range
    period: int  # T = nn.size - 2
    useg: npt.NDArray[np.float64]  # UNSHIFTED u[nn-1]/fs -> flow (fac), spectral (fft)
    uuseg: npt.NDArray[np.float64]  # UNSHIFTED uu[nn-1] -> flow (dpeak)
    useg_shifted: npt.NDArray[np.float64]  # DC-shifted useg -> timing only
    o1: int  # open-phase start (0 => no open phase); the shared O1 the seam masks on
    o2: int
    c1: int
    c2: int


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
    """Raw per-interval ``(f0, framek, frame_len_ok)`` over the ``len(gci)+1`` intervals.

    ``gci`` are 0-based sample indices (the `GciResult` convention); returns arrays
    of length ``len(gci)+1`` in the raw reference form (``framek`` 1-based,
    ``frame_len_ok`` as 0/1). The period is ``T = len(nn)-2`` and ``f0 = fs/T`` -- the reference's
    convention (see REFERENCE_NOTES, "Feature observations" V1: this makes ``f0``
    ``fs/(period-1)`` for interior cycles, not ``fs/period``).
    """
    cfg = config if config is not None else FeaturesConfig()
    segments = list(iter_cycle_segments(gci, n_samples))
    n_intervals = len(segments)
    f0 = np.zeros(n_intervals)
    framek = np.zeros(n_intervals)
    frame_len_ok = np.zeros(n_intervals)

    t_lo = fs / cfg.voicing_f0_max  # fs/400
    t_hi = fs / cfg.voicing_f0_min  # fs/40
    for ig, (a, b, nn) in enumerate(segments):
        framek[ig] = a + matlab_round((b - a) / 2)  # centre of the untrimmed interval
        period = nn.size - 2  # the reference's T = len(nn) - 2
        if t_lo < period < t_hi:
            frame_len_ok[ig] = 1.0
        with np.errstate(divide="ignore"):
            f0[ig] = fs / period
    return f0, framek, frame_len_ok
