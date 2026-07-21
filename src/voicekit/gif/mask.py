"""The closed-phase (``cp``) 0/1 analysis weight (REFERENCE_NOTES GIF2).

Builds the per-sample weight the closed-phase covariance solve runs under: ``1``
on the closed phase, ``0`` on the return phase after each GCI and on the open
phase up to the next GCI. The solve runs over the full analysis frames (GIF2's
locked design); this weight, not a restricted interval, is how the closed phase
enters.

Reimplemented from the reference ``cp`` mask, faithfully including its loop
*order* (the zeroings overlap, so order is load-bearing) and its inclusive-range
boundaries. Reimplemented from the algorithm description, not ported.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round
from voicekit.gif.config import ClosedPhaseConfig


def closed_phase_weight(
    gci: npt.NDArray[np.int64],
    goi: npt.NDArray[np.int64],
    n_samples: int,
    fs: float,
    config: ClosedPhaseConfig,
) -> npt.NDArray[np.float64]:
    """0/1 closed-phase weight over ``n_samples`` samples.

    ``gci`` are 0-based GCI positions; ``goi`` the gap-free per-cycle openings
    from `reconstruct_gois` (0-based, one per GCI, never absent). Returns a
    float64 array of length ``n_samples`` with values in ``{0.0, 1.0}``.

    The construction is done in the reference's 1-based indexing internally --
    ``w[1..n_samples]`` with an unused ``w[0]`` -- so each MATLAB inclusive range
    ``w(a:b)=0`` translates to the Python half-open ``w[a:b+1]=0`` uniformly and
    exactly, with no per-boundary 0-based arithmetic to get wrong. In particular
    the between-spurt line ``w(max(1,gci-cpDelay):gci)=0`` is inclusive of the
    GCI (its Python end is ``gci+1``), which a 0-based rendering can drop.

    Order (reproduced verbatim; the regions overlap):

    - boundary dummies: a GCI at 1 (resp. ``n_samples``) with a NaN opening is
      prepended (resp. appended) when the first (resp. last) real cycle's gap to
      the signal edge exceeds ``maxSamplesPerCycle`` -- so that edge cycle takes
      the between-spurt branch and its NaN opening is never indexed;
    - per consecutive GCI pair: if the gap exceeds ``maxSamplesPerCycle`` it is a
      between-voiced-spurt interval -- suppress only a ``cpDelay`` region ahead of
      the upcoming GCI and ``continue`` (skipping both lines below); otherwise
      suppress the return phase ``[gci, gci+cpDelay]`` then the open phase
      ``[goi, next_gci]``.

    The ``continue`` is the reference's entire NaN tolerance: only between-spurt
    cycles may carry a NaN opening (the boundary dummies), and they never reach
    the open-phase line. Within-spurt openings are always finite (guaranteed by
    `reconstruct_gois`).
    """
    max_spc = int(np.ceil(fs / config.min_f0))  # maxSamplesPerCycle = ceil(fs/minF0)
    cp_delay = int(matlab_round(config.cp_delay_s * fs))  # round(cpDelay*fs); MATLAB round

    # 1-based padded weight: index i is the reference's sample i (1..n_samples).
    w = np.ones(n_samples + 1, dtype=np.float64)

    g = [int(x) + 1 for x in np.asarray(gci, dtype=np.int64)]  # -> 1-based
    o: list[float] = [float(x) + 1 for x in np.asarray(goi, dtype=np.int64)]  # -> 1-based

    # Boundary dummies (reference: gci(1) at 1, gci(end) at n_samples).
    if g[0] > max_spc:
        g = [1, *g]
        o = [float("nan"), *o]
    if g[-1] < n_samples - max_spc:
        g = [*g, n_samples]
        o = [*o, float("nan")]

    for i in range(len(g) - 1):
        if g[i + 1] - g[i] > max_spc:
            # between voiced spurts: suppress a cpDelay region ahead of the GCI,
            # inclusive of the GCI (MATLAB w(max(1,gci-cpDelay):gci)=0).
            w[max(1, g[i] - cp_delay) : g[i] + 1] = 0.0
            continue
        # return phase: MATLAB w(gci:gci+cpDelay)=0
        w[g[i] : g[i] + cp_delay + 1] = 0.0
        # open phase: MATLAB w(goi:gci_next)=0
        w[int(o[i]) : g[i + 1] + 1] = 0.0

    return w[1 : n_samples + 1]  # drop the 1-based padding -> 0-based, length n_samples
