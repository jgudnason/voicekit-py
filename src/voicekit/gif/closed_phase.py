"""Closed-phase weighted-LP glottal inverse filtering (the ``cp`` method).

Reproduces the reference weighted-LP solve wrapper's closed-phase path: estimate
a per-frame AR model on the pre-emphasised signal under the closed-phase 0/1
weight (GIF2 mask), inverse-filter the original signal with those per-frame
coefficients, and de-emphasise -- yielding the glottal flow ``uu`` and its
integrated form ``u``. The full-frame solve with a 0/1 weight (not an
interval-restricted solve) is GIF2's locked design; the ``W^2`` weight convention
is GIF1.

This method is a weight-construction wrapper over the shared
`voicekit.gif.weighted_lp` core: it builds the cp 0/1 weight (from the
GIF6-reconstructed GOIs) and hands it to ``_weighted_lp_solve``; everything after
the weight -- the frame grid, pre-emphasis, GIF1 squaring, per-frame solve, GIF5
validity, inverse filter, de-emphasis -- is the method-independent core.

GIF5 (rank-degeneracy) is handled by **Option B**: a frame whose nonzero-weight
support falls below the model dimension is solved anyway (``lpc_covar`` returns
the minimum-norm solution -- the flow stays numerically pure, never NaN in the
signal), and the frame is flagged invalid. The NaN masking is a *downstream*
composition (`voicekit.features` turns invalid frames into per-cycle NaN via the
existing ``apply_cycle_mask`` seam); the weighter never injects a signal-level
NaN. See REFERENCE_NOTES GIF5.

Reimplemented from the reference algorithm description, not ported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from voicekit.gif.config import ClosedPhaseConfig
from voicekit.gif.goi_selection import reconstruct_gois
from voicekit.gif.mask import closed_phase_weight
from voicekit.gif.weighted_lp import WeightedLpResult, _weighted_lp_solve

__all__ = ["ClosedPhaseResult", "closed_phase_gif"]


@dataclass(frozen=True)
class ClosedPhaseResult(WeightedLpResult):
    """Closed-phase output: the shared weighted-LP result plus cp's reconstructed GOIs.

    Extends `WeightedLpResult` (``u``, ``uu``, ``weight``, ``frame_starts``,
    ``frame_valid``) with ``goi`` -- the gap-free per-cycle openings the cp 0/1 weight
    was built from (the reference GOI-selection step, GIF6), exposed for inspection /
    golden-master. The three continuous-weight methods are gci-only and return the bare
    `WeightedLpResult`; ``goi`` lives here, on cp's own result, not on the shared type.
    """

    goi: npt.NDArray[np.int64]


def closed_phase_gif(
    signal: npt.NDArray[np.float64],
    fs: float,
    gci: npt.NDArray[np.int64],
    goi_candidates: npt.NDArray[np.int64],
    config: ClosedPhaseConfig | None = None,
) -> ClosedPhaseResult:
    """Closed-phase glottal inverse filtering of ``signal``.

    ``gci`` and ``goi_candidates`` are the 0-based `GciResult` fields returned by
    ``yaga`` (returned, not re-detected). Runs at the signal's native ``fs``
    (GIF7): every constant is a formula in ``fs``, no resample.
    """
    cfg = config if config is not None else ClosedPhaseConfig()
    sp = np.asarray(signal, dtype=np.float64)
    nsp = sp.size
    gci = np.asarray(gci, dtype=np.int64)

    # GOI-selection reconstruction (GIF6) -> the gap-free openings the mask needs.
    goi = reconstruct_gois(gci, goi_candidates, cfg.apop)
    weight = closed_phase_weight(gci, goi, nsp, fs, cfg)

    core = _weighted_lp_solve(
        sp,
        fs,
        weight,
        preemph_hz=cfg.preemph_hz,
        frame_len_s=cfg.frame_len_s,
        frame_hop_s=cfg.frame_hop_s,
    )
    return ClosedPhaseResult(
        u=core.u,
        uu=core.uu,
        weight=core.weight,
        frame_starts=core.frame_starts,
        frame_valid=core.frame_valid,
        goi=goi,
    )
