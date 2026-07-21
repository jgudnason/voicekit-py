"""Typed configuration for the weighted-LP glottal inverse filtering methods.

No global mutable state (DESIGN.md): every algorithm takes an explicit config.
The closed-phase parameters below are each fixed **from the reference source**
(the gate rounds, REFERENCE_NOTES GIF2/GIF5/GIF7), not fitted to any fixture --
they are rule-1 defaults, cited to source, not tuned to an outcome.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClosedPhaseConfig:
    """Parameters for the closed-phase (``cp``) weighted-LP method.

    Every default is the reference value, cited; none is fixture-derived.

    - ``cp_delay_s``: the return-phase suppression after each GCI, in seconds.
      Reference ``projParam.m`` ``par.wpar.cpDelay = 0.9e-3`` ("closed analysis
      begins after GCI"). Applied as ``round(cp_delay_s * fs)`` samples.
    - ``min_f0``: the lowest assumed F0, in Hz. Reference ``minF0 = 50``. Sets
      ``maxSamplesPerCycle = ceil(fs / min_f0)`` -- the between-voiced-spurt gap
      threshold.
    - ``apop``: the a-priori-optimal-point fraction of the larynx cycle for the
      GOI-selection step, ``voicebox('dy_cpfrac') = 0.3`` (presumed closed-phase
      fraction). Used as ``coc = gci + ceil(apop * dgci)``.
    - ``preemph_hz``: pre-emphasis cutoff for the AR estimate, in Hz. Reference
      ``par.mpar.f_preemph = 5``.
    - ``frame_len_s`` / ``frame_hop_s``: analysis-frame length / increment, in
      seconds. Reference ``par.fpar.wl = 32e-3`` / ``inc = 16e-3``. Frames are
      ``round(fs * .)`` samples; the order is ``nar = ceil(fs / 1000)`` (one pole
      per 1000 Hz), computed from ``fs`` at call time (not stored -- it has no
      fs-independent value).
    """

    cp_delay_s: float = 0.9e-3
    min_f0: float = 50.0
    apop: float = 0.3
    preemph_hz: float = 5.0
    frame_len_s: float = 32e-3
    frame_hop_s: float = 16e-3
