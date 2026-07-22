"""AME (Attenuated Main Excitation) weighted-LP glottal inverse filtering.

Alku's AME method: down-weight ("attenuate") the main-excitation region -- the
interval straddling / just before each GCI where the largest prediction error
occurs -- to a positive floor ``d``, forcing the LP fit onto the rest of the cycle.
A weight-construction wrapper over the shared `voicekit.gif.weighted_lp` core (only
the weight differs between methods, GIF8).

Unlike the closed-phase 0/1 mask and agauss's clamped Gaussian, AME's weight never
reaches zero (floor ``d > 0``), so its nonzero-weight support is the full frame on
every frame -- there is no GIF5 rank-deficiency for AME on any input: ``frame_valid``
is all-true and the downstream invalid-frame mask is inherited but never triggered.

Credit: P. Alku et al., "Improved formant frequency estimation from ...".
Reimplemented from the reference algorithm description, not ported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round
from voicekit.gif.weighted_lp import (
    _FRAME_HOP_S,
    _FRAME_LEN_S,
    _PREEMPH_HZ,
    WeightedLpResult,
    _weighted_lp_solve,
)


@dataclass(frozen=True)
class AmeConfig:
    """Parameters for the AME (attenuated main excitation) weighted-LP method.

    Every default is the reference value, cited (``projParam`` ``case 'ame'``); none
    fitted.

    - ``d``: attenuation floor (Alku Fig 1). Reference ``d = 0.01``. The main-
      excitation region is down-weighted to ``d``, never zeroed -- so support stays
      full and no GIF5 rank-deficiency arises.
    - ``duration_quotient`` (DQ): attenuation-region width as a fraction of the pitch
      period ``T``. Reference ``DQ = 0.4``.
    - ``position_quotient`` (PQ): where the region sits -- ``round(PQ*DQ*T)`` samples
      before the GCI. Reference ``PQ = 0.8``.
    - ``ramp_len`` (rlen): linear ramp length in samples on each side of the well.
      Reference ``rlen = 3``.
    - ``min_f0``: lowest assumed F0 (Hz). Reference ``minF0 = 50``. Sets
      ``maxSamplesPerCycle = ceil(fs/min_f0)`` -- AME's own formula, NOT agauss's
      half-cycle ``0.5*ceil(fs/min_f0)``; the two methods' caps differ and are
      deliberately not single-sourced.
    - framing / pre-emphasis: shared across every weighted-LP method (`weighted_lp`).
    """

    d: float = 0.01
    duration_quotient: float = 0.4
    position_quotient: float = 0.8
    ramp_len: int = 3
    min_f0: float = 50.0
    preemph_hz: float = _PREEMPH_HZ
    frame_len_s: float = _FRAME_LEN_S
    frame_hop_s: float = _FRAME_HOP_S


def ame_weight(
    gci: npt.NDArray[np.int64],
    n_samples: int,
    fs: float,
    config: AmeConfig | None = None,
) -> npt.NDArray[np.float64]:
    """AME analysis weight over ``n_samples`` samples (``1`` elsewhere, ``d`` in the well).

    ``gci`` are **1-based** GCI positions (the reference indexing ``weightsForLP``
    uses); the returned length-``n_samples`` weight has index ``i`` = sample ``i+1``.
    ``ame_gif`` applies the 0-based -> 1-based conversion at its boundary. AME reads
    ``gci`` only. Attenuates a well of width ``round(DQ*T)`` to the floor ``d``,
    positioned ``round(PQ*DQ*T)`` before each GCI with ``rlen``-sample linear ramps;
    it never reaches 0, so effective support is the full frame.
    """
    cfg = config if config is not None else AmeConfig()
    d, dq, pq, rlen, min_f0 = (
        cfg.d,
        cfg.duration_quotient,
        cfg.position_quotient,
        cfg.ramp_len,
        cfg.min_f0,
    )
    max_spc = np.ceil(fs / min_f0)  # AME: ceil(fs/minF0) -- NOT agauss's 0.5*ceil
    gci = np.asarray(gci, dtype=np.float64)
    t = np.append(np.diff(gci), gci[-1] - gci[-2])  # per-cycle period, last extended
    over = np.where(t > max_spc)[0]  # between-spurt handling (unreached on fixtures)
    for i in over:
        t[i] = t[i - 1]
    dramp = np.linspace(1, d, rlen + 1)
    uramp = np.linspace(d, 1, rlen + 1)
    w = np.ones(n_samples)
    for ii, g in enumerate(gci):
        ts = int(g - matlab_round(pq * dq * t[ii]))
        tsm = ts - rlen
        w[tsm - 1 : ts] = dramp  # MATLAB w(tsm:ts) = dramp, 1-based inclusive
        te = ts + int(matlab_round(dq * t[ii]))
        tep = te + rlen
        w[ts - 1 : te] = d
        w[te - 1 : tep] = uramp
    return w


def ame_gif(
    signal: npt.NDArray[np.float64],
    fs: float,
    gci: npt.NDArray[np.int64],
    *,
    config: AmeConfig | None = None,
) -> WeightedLpResult:
    """AME glottal inverse filtering of ``signal``.

    ``gci`` are the 0-based `GciResult.gci` closure instants (returned by ``yaga``,
    not re-detected). AME reads ``gci`` only -- no ``goi`` / ``goi_candidates``. Runs
    at native ``fs`` (GIF7). Returns the bare `WeightedLpResult` (no ``goi``); AME's
    positive weight floor means ``frame_valid`` is all-true.
    """
    cfg = config if config is not None else AmeConfig()
    sp = np.asarray(signal, dtype=np.float64)
    gci = np.asarray(gci, dtype=np.int64)
    # weightsForLP indexes 1-based; GciResult.gci is 0-based (as closed_phase_weight
    # converts internally too). Convert at this boundary.
    weight = ame_weight(gci + 1, sp.size, fs, cfg)
    return _weighted_lp_solve(
        sp,
        fs,
        weight,
        preemph_hz=cfg.preemph_hz,
        frame_len_s=cfg.frame_len_s,
        frame_hop_s=cfg.frame_hop_s,
    )
