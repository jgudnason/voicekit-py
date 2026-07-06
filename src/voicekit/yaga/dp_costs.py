"""Precomputable per-candidate DP cost terms for YAGA GCI selection.

The dynamic program (piece 5) scores each candidate glottal closure with
several cost terms. Four of them are pure functions of the candidate set and
the upstream signals, so they are precomputed here as per-candidate vectors:

    * phase-slope cost and the projected-candidate penalty (from candidate
      assembly -- merging the zero-crossing and phase-slope-projected streams);
    * Frobenius-norm energy cost (the Ma/Kamp/Willems measure at each
      candidate, normalized by a running maximum);
    * closed-phase (anticausal) energy cost.

The remaining two DP terms -- waveform similarity and pitch deviation -- are
*path* dependent (a candidate's waveform-similarity cost depends on the
previous selected GCI, and pitch deviation on the previous two), so they
cannot be per-candidate columns; they live with the DP recursion in piece 5.

These vectors are produced *unweighted*: the DP applies the cost weights when
it sums them, so the weights are the DP's parameters, not this module's.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), DYPSA, IEEE
    TASLP 15(1), 34-43.
    C. Ma, Y. Kamp & L. F. Willems (1994), "A Frobenius norm approach to
    glottal closure detection", IEEE Trans. Speech Audio Proc. 2, 258-265.

    Reference implementation: the ``frobfun``, ``fnrg`` and closed-phase code
    of the VOICEBOX-bundled ``dypsagoi.m``. Reimplemented from the algorithm
    descriptions, not ported.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit.yaga._matlab_compat import matlab_round

# Structural constants, hardcoded in the reference (not tunable parameters).
_BOUNDARY_MARGIN_S = 0.01  # candidates within this of either signal end are dropped
_LEAKY_POLE = 0.99  # closed-phase leaky-integrator pole
_CLOSED_PHASE_SCALE = 0.5  # closed-phase normalization factor


@dataclass(frozen=True)
class FrobeniusConfig:
    """Parameters of the Frobenius-norm energy cost (voicebox ``dy_ew*``/``dy_fxminf``)."""

    ew_taper: float = 0.001  # taper (ramp) length of the energy window (s)
    ew_len: float = 0.003  # flat length of the energy window (s)
    ew_dly: float = 0.0008  # window delay / alignment shift (s)
    fxminf: float = 60.0  # min larynx frequency for the running-max normalization (Hz)


@dataclass(frozen=True)
class CandidateSet:
    """Assembled GCI candidates and their per-candidate costs.

    ``positions`` are 0-based sample indices (compare to the MATLAB capture's
    1-based ``dp_gcic`` column 1 as ``positions + 1``). ``is_zero_crossing``
    is True for group-delay zero-crossing candidates, False for phase-slope
    projected ones. ``phase_slope_cost`` is the DP's ``Ch`` term.
    """

    positions: npt.NDArray[np.int64]
    is_zero_crossing: npt.NDArray[np.bool_]
    phase_slope_cost: npt.NDArray[np.float64]

    @property
    def projected_penalty(self) -> npt.NDArray[np.float64]:
        """The ``(1 - flag)/2`` penalty: 0 for zero-crossing, 0.5 for projected."""
        return (1.0 - self.is_zero_crossing.astype(np.float64)) / 2.0


def assemble_candidates(
    zcr_positions: npt.NDArray[np.float64],
    zcr_slopes: npt.NDArray[np.float64],
    projected_positions: npt.NDArray[np.float64],
    gdwav_length: int,
    fs: float,
) -> CandidateSet:
    """Merge the zero-crossing and projected candidate streams for the DP.

    Zero-crossing candidates round to integer positions (flag True, phase-slope
    cost ``0.5 + slope``); projected candidates keep their integer positions
    (flag False, cost 0). The merged set is sorted by (position, flag) -- so a
    projected candidate precedes a co-located zero-crossing one -- and trimmed
    of anything within ``0.01*fs`` of either end of the group-delay function.

    All positions are 0-based; inputs are as the piece-2/3 modules return them.
    """
    zcr_pos = matlab_round(zcr_positions).astype(np.int64)
    proj_pos = matlab_round(projected_positions).astype(np.int64)

    positions = np.concatenate([zcr_pos, proj_pos])
    is_zcr = np.concatenate(
        [np.ones(zcr_pos.size, dtype=bool), np.zeros(proj_pos.size, dtype=bool)]
    )
    ch = np.concatenate([0.5 + zcr_slopes, np.zeros(proj_pos.size)])

    # Sort by position, then flag (False before True) so a projected candidate
    # precedes a co-located zero-crossing one, matching MATLAB sortrows.
    order = np.lexsort((is_zcr, positions))
    positions, is_zcr, ch = positions[order], is_zcr[order], ch[order]

    # Boundary trim, written via the 1-based position to mirror the reference
    # condition 0.01*fs < gcic < length(gdwav) - 0.01*fs.
    margin = _BOUNDARY_MARGIN_S * fs
    pos_1based = positions + 1
    keep = (margin < pos_1based) & (pos_1based < gdwav_length - margin)
    return CandidateSet(
        positions=positions[keep],
        is_zero_crossing=is_zcr[keep],
        phase_slope_cost=ch[keep],
    )


def frobenius_energy_function(
    s_used: npt.NDArray[np.float64], fs: float, config: FrobeniusConfig | None = None
) -> npt.NDArray[np.float64]:
    """The Frobenius-norm energy function of the (pre-emphasized) speech.

    A trapezoidal window (linear ramp up over ``p`` taps, flat, ramp down over
    ``p``) filters the signal energy; the leading ``round((p+m-1)/2)+offset``
    samples are dropped so the result is aligned to the original samples (this
    is the reference's ``frobfun``; ``p``, ``m``, ``offset`` from the config).
    """
    cfg = config if config is not None else FrobeniusConfig()
    sp = np.asarray(s_used, dtype=np.float64)
    p = int(matlab_round(cfg.ew_taper * fs))
    m = int(matlab_round(cfg.ew_len * fs))
    offset = int(matlab_round(cfg.ew_dly * fs))

    w = np.full(m + p, p + 1, dtype=np.float64)
    w[:p] = np.arange(1, p + 1)
    w[m : m + p] = np.arange(p, 0, -1)
    w = w / (p + 1)

    frob = scipy.signal.lfilter(w, [1.0], sp**2)
    drop = int(matlab_round((p + m - 1) / 2)) + offset
    return np.asarray(frob[drop:])


def frobenius_energy_cost(
    positions: npt.NDArray[np.int64],
    fnwav: npt.NDArray[np.float64],
    fs: float,
    config: FrobeniusConfig | None = None,
) -> npt.NDArray[np.float64]:
    """Frobenius energy cost ``0.5 - fnwav/runningmax(fnwav)`` at each candidate.

    The running maximum (window ``round(fs/fxminf)``) is a causal trailing max,
    then shifted by ``floor(mm/2)`` to centre it and end-padded with the max of
    the last ``ceil(mm/2)+1`` samples -- so candidates near the end are
    normalized against that tail maximum. ``positions`` are 0-based.
    """
    cfg = config if config is not None else FrobeniusConfig()
    frob = np.asarray(fnwav, dtype=np.float64)
    mm = int(matlab_round(fs / cfg.fxminf))
    half = mm // 2  # floor(mm/2)
    ceil_half = mm - half  # ceil(mm/2)

    trailing_max = _causal_running_max(frob, mm)
    pad = frob[len(frob) - ceil_half - 1 :].max()  # max of last ceil(mm/2)+1 samples
    mfrob = np.concatenate([trailing_max[half:], np.full(half, pad)])

    rfr = frob / mfrob
    idx = matlab_round(positions.astype(np.float64)).astype(np.int64)  # no-op on ints, per source
    return np.asarray(0.5 - rfr[idx], dtype=np.float64)


def closed_phase_cost(
    udash: npt.NDArray[np.float64], positions: npt.NDArray[np.int64]
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Anticausal (aencost) and causal (cencost) closed-phase energy costs.

    The residual is leaky-integrated; ``aencost[i]`` is the mean of that signal
    over the inclusive sample range between candidate ``i`` and ``i+1`` (the
    last entry stays 0). It is then scaled by ``0.5/mean(|aencost|)`` -- with
    the trailing 0 included in that mean -- and ``cencost`` is ``aencost``
    shifted one candidate later. ``positions`` are 0-based, ascending.
    """
    u = scipy.signal.lfilter([1.0], [1.0, -_LEAKY_POLE], np.asarray(udash, dtype=np.float64))
    pos = np.asarray(positions, dtype=np.int64)
    aencost = np.zeros(pos.size)
    for i in range(pos.size - 1):
        aencost[i] = u[pos[i] : pos[i + 1] + 1].mean()  # 1-based a:b -> 0-based [a:b+1]
    aencost = _CLOSED_PHASE_SCALE * aencost / np.mean(np.abs(aencost))
    cencost = np.concatenate([[0.0], aencost[:-1]])
    return aencost, cencost


def _causal_running_max(x: npt.NDArray[np.float64], mm: int) -> npt.NDArray[np.float64]:
    """Trailing running maximum: ``y[p] = max(x[max(0, p-mm+1) : p+1])``.

    Matches MATLAB ``v_maxfilt(x, 1, mm)`` (samples before the start are -inf,
    so they never win the max).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.empty_like(x)
    for p in range(x.size):
        y[p] = x[max(0, p - mm + 1) : p + 1].max()
    return y
