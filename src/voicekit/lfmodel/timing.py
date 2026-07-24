"""Liljencrants-Fant (LF) glottal-pulse *timing* quantities.

The LF model parametrises one glottal-flow-derivative pulse by the dimensionless
shape parameters ``Rk``, ``Rg`` (and ``Ra``, ``Ee``, not needed for timing) at a
fundamental ``f0``. This module computes only the *timing* landmarks that follow
in closed form from ``Rk``, ``Rg`` and ``f0`` -- it does **not** synthesise a pulse
(that needs the ``Ee``/``Ra``/epsilon machinery) and is deliberately not a GCI
definition: the mapping from these instants to a scored reference is the caller's
(see ``validation/openglot``), kept out of ``src`` so the library stays
definition-agnostic.

- ``Tp``  time of the flow maximum (derivative zero-crossing), ``0.5 / (Rg*f0)``.
- ``Tn``  ``Rk * Tp`` -- sets the closing-phase duration relative to the opening.
- ``Te``  instant of maximum negative flow derivative (the excitation / closure
          instant), ``(1 + Rk) / (2*Rg*f0)``.
- ``Tb``  return-phase duration after ``Te``, ``(1 - (Rk+1)/(2*Rg)) / f0``, so the
          pulse period ``Te + Tb = 1/f0``.

Reimplemented from the published Fant/Liljencrants/Lin relations. The identical
relations appear in OpenGlot's shipped generator (``lf.m``); this module is a
first-principles reimplementation, not a port.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LfTiming:
    """The LF timing landmarks (seconds) for one ``(Rk, Rg, f0)`` parameter set.

    All four are exact closed-form functions of the shape parameters and ``f0``;
    nothing here is fitted. ``te`` is the instant a GCI detector responds to (the
    maximum negative flow derivative); the rest are provided because a caller
    reconstructing the pulse grid needs them.
    """

    tp: float  # flow maximum
    tn: float  # closing-phase landmark, Rk * tp
    te: float  # maximum negative derivative (excitation instant)
    tb: float  # return-phase duration after te; te + tb == 1/f0


def lf_timing(rk: float, rg: float, f0: float) -> LfTiming:
    """LF timing landmarks from the dimensionless shape parameters and ``f0`` (Hz)."""
    if f0 <= 0:
        raise ValueError(f"f0 must be positive, got {f0}")
    if rg <= 0:
        raise ValueError(f"Rg must be positive, got {rg}")
    tp = 0.5 / (rg * f0)
    tn = rk * tp
    te = (1.0 + rk) / (2.0 * rg * f0)
    tb = (1.0 - (rk + 1.0) / (2.0 * rg)) / f0
    return LfTiming(tp=tp, tn=tn, te=te, tb=tb)
