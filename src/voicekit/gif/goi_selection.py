"""Reconstruct the reference's gap-free GOI sequence for the closed-phase mask.

The closed-phase mask is built from the reference GOI-*selection* step's output,
NOT from ``GciResult.goi`` (the DP/postGOI pairing) -- the two diverge on 55/55
cycles at 16 kHz (REFERENCE_NOTES GIF6). This module reconstructs that selection
step from the exposed ``GciResult.goi_candidates``.

The selection step (a candidate-selection method due to the maintainer; see
GIF6): for each cycle, take the a-priori opening point ``coc = gci + ceil(APOP *
dgci)`` and pick the GOI candidate strictly inside the cycle nearest to ``coc``;
when the cycle has no candidate, fall back to ``coc`` itself -- so the output is
total (never absent). This gap-free-ness is exactly what lets the ``cp`` mask's
open-phase line index a finite GOI on every within-spurt cycle.

Reimplemented from the reference algorithm description, not ported.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def reconstruct_gois(
    gci: npt.NDArray[np.int64],
    goi_candidates: npt.NDArray[np.int64],
    apop: float,
) -> npt.NDArray[np.int64]:
    """Per-cycle GOI positions (0-based), one per GCI, gap-free (never absent).

    ``gci`` and ``goi_candidates`` are 0-based sorted positions (as
    `GciResult.gci` / `GciResult.goi_candidates` return them). ``apop`` is the
    a-priori-optimal-point fraction (``ClosedPhaseConfig.apop``).

    Matches the reference selection step:

    - ``dgci = diff(gci)`` with the last cycle's length repeated (zero-order
      approximation for the final, open-ended cycle);
    - ``coc = gci[i] + ceil(apop * dgci[i])`` -- **ceil**, not round (VUV9's
      round-vs-ceil class; the reference uses ``ceil``);
    - candidates strictly inside ``(gci[i], gci[i] + dgci[i])`` (both bounds
      exclusive); nearest to ``coc`` by squared distance; ``coc`` if none.
    """
    gci = np.asarray(gci, dtype=np.int64)
    cand = np.asarray(goi_candidates, dtype=np.int64)
    n = gci.size
    if n == 0:
        return np.empty(0, dtype=np.int64)

    dgci = np.diff(gci)
    # zero-order approximation for the last (open-ended) cycle; MATLAB's
    # dgci(end+1) = dgci(end). A lone GCI has no interval -> 0.
    last = int(dgci[-1]) if dgci.size else 0
    dgci = np.append(dgci, last)

    goi = np.empty(n, dtype=np.int64)
    for i in range(n):
        coc = int(gci[i]) + int(np.ceil(apop * dgci[i]))  # a-priori point; ceil (VUV9)
        lo, hi = int(gci[i]), int(gci[i]) + int(dgci[i])
        inside = cand[(cand > lo) & (cand < hi)]  # strictly inside the cycle
        if inside.size:
            goi[i] = int(inside[np.argmin((inside - coc) ** 2)])  # nearest to coc
        else:
            goi[i] = coc  # a-priori fallback -- never absent
    return goi
