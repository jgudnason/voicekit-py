"""Gaussian-weighted LP glottal inverse filtering (Zalazar et al. 2024).

Two Zalazar-family methods live here: ``rgauss`` (symmetric Gaussian) and, added
with its own commit, ``agauss`` (asymmetric). Each down-weights a Gaussian
neighbourhood of every GCI, subtracted from 1 -- a weight-construction wrapper over
the shared `voicekit.gif.weighted_lp` core (only the weight differs, GIF8).

The Gaussian exponent is the proper ``exp(-0.5 * x^2 / sig^2)`` form -- the
authoritative ``weightsForLP`` revision (GIF4); the ``-0.5``-absent predecessor is
superseded and NOT used.

Credit: L. Zalazar, G. Schlotthauer et al., "Symmetric and asymmetric Gaussian
weighted linear prediction for voice inverse filtering", 2024. Reimplemented from
the algorithm description, not ported.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from voicekit.gif.weighted_lp import (
    _FRAME_HOP_S,
    _FRAME_LEN_S,
    _PREEMPH_HZ,
    WeightedLpResult,
    _weighted_lp_solve,
)


@dataclass(frozen=True)
class RgaussConfig:
    """Parameters for the symmetric Gaussian (rgauss) weighted-LP method.

    Reference values (``projParam`` ``case 'rgauss'``; Zalazar et al. 2024); none
    fitted.

    - ``kappa``: notch depth. Reference ``kappa = 0.9`` -- the weight dips to
      ``1 - kappa`` at each GCI centre, so it is strictly positive (no hard zeros).
    - ``sig``: Gaussian std, in samples. Reference ``sig = sqrt(50)`` (so
      ``sig^2 = 50``). A fixed sample count -- NOT fs-scaled -- so at 8 kHz the notch
      is physically wider in time than at 16 kHz; that is the source value (Rule-1),
      ledgered as an item-9 consideration, not tuned here.
    - framing / pre-emphasis: shared across every weighted-LP method (`weighted_lp`).
    """

    kappa: float = 0.9
    sig: float = math.sqrt(50.0)
    preemph_hz: float = _PREEMPH_HZ
    frame_len_s: float = _FRAME_LEN_S
    frame_hop_s: float = _FRAME_HOP_S


def rgauss_weight(
    gci: npt.NDArray[np.int64],
    n_samples: int,
    fs: float,
    config: RgaussConfig | None = None,
) -> npt.NDArray[np.float64]:
    """Symmetric-Gaussian weight over ``n_samples`` samples: ``1 - sum kappa*N(gci, sig)``.

    ``gci`` are **1-based** GCI positions (the reference indexing ``weightsForLP``
    uses); index ``i`` of the return = sample ``i+1``. ``rgauss_gif`` converts at its
    boundary. rgauss reads ``gci`` only. **Strictly positive everywhere** (minimum
    ``~ 1 - kappa = 0.1 > 0`` -- the summed neighbour tails are negligible at the
    fixture spacings), so effective support is the full frame BY CONSTRUCTION: there
    is no hard zero and no GIF5 rank-deficiency for rgauss on any input.
    """
    cfg = config if config is not None else RgaussConfig()
    kappa = cfg.kappa
    sig2 = cfg.sig**2  # reference forms sig2 = sig^2 from sig = sqrt(50)
    nn = np.arange(1, n_samples + 1, dtype=np.float64)
    gg = np.zeros(n_samples)
    for g in gci:
        gg += kappa * np.exp(-0.5 * (nn - g) ** 2 / sig2)
    return 1.0 - gg


def rgauss_gif(
    signal: npt.NDArray[np.float64],
    fs: float,
    gci: npt.NDArray[np.int64],
    *,
    config: RgaussConfig | None = None,
) -> WeightedLpResult:
    """rgauss glottal inverse filtering of ``signal``.

    ``gci`` are the 0-based `GciResult.gci` closure instants. rgauss reads ``gci``
    only -- no ``goi``. Runs at native ``fs`` (GIF7). Returns the bare
    `WeightedLpResult` (no ``goi``); rgauss's strictly-positive weight means
    ``frame_valid`` is all-true by construction.
    """
    cfg = config if config is not None else RgaussConfig()
    sp = np.asarray(signal, dtype=np.float64)
    gci = np.asarray(gci, dtype=np.int64)
    # weightsForLP indexes 1-based; GciResult.gci is 0-based. Convert at the boundary.
    weight = rgauss_weight(gci + 1, sp.size, fs, cfg)
    return _weighted_lp_solve(
        sp,
        fs,
        weight,
        preemph_hz=cfg.preemph_hz,
        frame_len_s=cfg.frame_len_s,
        frame_hop_s=cfg.frame_hop_s,
    )
