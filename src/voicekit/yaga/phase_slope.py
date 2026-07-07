"""Phase-slope projection of the group-delay function.

The third YAGA front-end step. Zero crossings of the energy-weighted group
delay give most glottal-closure candidates, but some closures produce only
a *turning point* that approaches zero without crossing it -- a local
maximum still below zero, or a local minimum still above zero. Phase-slope
projection recovers those: from the midpoint of the failed approach it
extrapolates, along unit slope, to where the crossing would have been.

Unit slope is not a tuning choice: the group delay is measured in samples,
so its value at a point *is* a sample offset, which forces the projection
``proj = midpoint - round(value)`` dimensionally.

This stage reads only the group-delay function (the reference passes ``fs``
but never uses it). It has no tunable parameters -- the zero thresholds and
the unit slope are structural -- so there is no config object. It does no
deduplication, proximity merging, or boundary trimming; those happen later
when the projected and zero-crossing candidates are combined for the DP.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), "Estimation
    of Glottal Closure Instants in Voiced Speech using the DYPSA Algorithm",
    IEEE TASLP 15(1), 34-43.

    Reference implementation: the ``psp`` subfunction (and its ``zcr``/``zcrp``
    turning-point finder) of the VOICEBOX-bundled ``dypsagoi.m``.
    Reimplemented from the algorithm description, not ported.
"""

import numpy as np
import numpy.typing as npt

from voicekit._matlab_compat import matlab_round as _matlab_round


def _falling_crossings(x: npt.NDArray[np.float64]) -> npt.NDArray[np.int64]:
    """Indices where ``x`` steps strictly +1 -> -1 in sign, snapped to the
    sample nearest zero (ties keep the earlier sample)."""
    z1 = np.asarray(np.nonzero(np.diff(np.sign(x)) == -2)[0], dtype=np.int64)
    if z1.size == 0:
        return z1
    take_next = np.abs(x[z1 + 1]) < np.abs(x[z1])
    return np.asarray(z1 + take_next.astype(np.int64), dtype=np.int64)


def _turning_points(gdot: npt.NDArray[np.float64]) -> npt.NDArray[np.int64]:
    """Sorted indices of the extrema of ``g`` from its derivative ``gdot``:
    falling crossings (maxima), rising crossings (minima), and exact zeros of
    ``gdot`` followed by a nonzero."""
    maxima = _falling_crossings(gdot)
    minima = _falling_crossings(-gdot)
    nxt = np.concatenate([gdot[1:], [0.0]])
    exact = np.nonzero((gdot == 0) & (nxt != 0))[0]
    return np.sort(np.concatenate([exact, maxima, minima]))


def phase_slope_projection(gdwav: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Project GCI candidates from the turning points of ``gdwav``.

    ``gdwav`` is the aligned, sign-flipped group delay from
    `energy_weighted_group_delay`; projected candidates are already in its
    (original-signal) sample frame, so no further offset is applied. Returns
    the sorted, 0-based candidate sample locations (empty if none).
    """
    g = np.asarray(gdwav, dtype=np.float64)
    if g.ndim != 1:
        raise ValueError(f"gdwav must be 1-D, got shape {g.shape}")

    gdot = np.concatenate([np.diff(g), [0.0]])
    gdotdot = np.concatenate([np.diff(gdot), [0.0]])
    tp = _turning_points(gdot)
    if tp.size == 0:
        return np.empty(0)

    kind = np.sign(gdotdot[tp])  # -1 at a maximum, +1 at a minimum
    value = g[tp]
    rows = np.arange(tp.size)

    # Negative maxima: maxima below zero, excluding the very first turning
    # point (it has no predecessor to take a midpoint from). Project from the
    # midpoint between the preceding turning point and the maximum.
    neg = rows[(kind == -1) & (value < 0) & (rows != 0)]
    mid_n = tp[neg - 1] + _matlab_round(0.5 * (tp[neg] - tp[neg - 1])).astype(np.int64)
    nz = mid_n - _matlab_round(g[mid_n]).astype(np.int64)

    # Positive minima: minima above zero. Project from the midpoint between the
    # minimum and the following turning point; drop the last one if it is the
    # final turning point (no successor).
    pos = rows[(kind == 1) & (value > 0)]
    if pos.size and pos[-1] == tp.size - 1:
        pos = pos[:-1]
    mid_p = tp[pos] + _matlab_round(0.5 * (tp[pos + 1] - tp[pos])).astype(np.int64)
    pz = mid_p - _matlab_round(g[mid_p]).astype(np.int64)

    return np.sort(np.concatenate([nz, pz])).astype(np.float64)
