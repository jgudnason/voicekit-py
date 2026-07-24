"""Shared machinery for the weighted-LP glottal inverse filtering methods.

Every method in ``voicekit.gif`` (closed-phase, AME, the Gaussian variants) is the
SAME solve under a different per-sample weight: estimate a per-frame AR model on the
pre-emphasised signal under the method's weight, inverse-filter the original signal,
de-emphasise -- yielding the glottal flow ``uu`` and its integrated form ``u``. Only
the weight vector changes between methods (REFERENCE_NOTES GIF8). This module is that
method-independent core -- the frame grid, pre-emphasis, the GIF1 ``W^2`` weight
convention, the per-frame covariance solve, the GIF5 rank-validity flag, the inverse
filter and de-emphasis -- so each method is a thin weight-construction wrapper over it.

Reimplemented from the reference algorithm description, not ported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit._matlab_compat import matlab_round
from voicekit.lpc.covariance import lpc_covar
from voicekit.lpc.frames import inverse_filter_frames

# Framing / pre-emphasis constants, shared by every weighted-LP method: the reference
# ``projParam`` ``fpar.wl`` / ``fpar.inc`` analysis grid and ``mpar.f_preemph`` cutoff.
# Genuine coupling -- all methods run on the same grid and pre-emphasis and must change
# together -- so single-sourced here (the per-method configs reference these). NOT the
# same as ``features/flow_derivation``'s ``f_preemph`` (10 Hz, the IAIF flow-derivation
# de-emphasis): that is a different constant, coincidence not coupling, left as-is.
_PREEMPH_HZ = 5.0
_FRAME_LEN_S = 32e-3
_FRAME_HOP_S = 16e-3


@dataclass(frozen=True)
class WeightedLpResult:
    """Output of the shared weighted-LP solve (method-independent).

    ``uu`` is the glottal flow derivative (the inverse-filtered signal); ``u`` its
    de-emphasised (integrated) form -- both length ``n_samples``, numerically pure
    (never NaN). ``weight`` is the per-sample analysis weight the solve ran under.

    ``frame_starts`` are the 0-based analysis-frame start samples; ``frame_valid`` is
    the per-frame GIF5 validity flag (``False`` where the frame's nonzero-weight
    support fell below the model dimension, so its AR is the minimum-norm solution of
    a rank-deficient system). The per-frame flag is turned into per-cycle NaN
    downstream (`voicekit.features.apply_invalid_frame_mask`), not here.

    ``frame_support`` is the per-frame nonzero-weight count over the predicted
    samples, and ``model_dim`` the dimension it is tested against (``nar`` lags plus
    one DC term). ``frame_valid`` is exactly ``frame_support >= model_dim`` -- the
    count is published so that a *margin* is observable, not only the boolean it
    collapses to. Distance from the rank-deficiency boundary is the quantity that
    says whether a healthy-looking run is nowhere near degeneracy or one cycle away
    from it (REFERENCE_NOTES GIF12: agauss's clamp makes full support a measured
    fact, not a constructed one, so corpus data can reopen the GIF5 path). Reporting
    the minimum alone hides the tail; consumers should keep the distribution.
    """

    u: npt.NDArray[np.float64]
    uu: npt.NDArray[np.float64]
    weight: npt.NDArray[np.float64]
    frame_starts: npt.NDArray[np.int64]
    frame_valid: npt.NDArray[np.bool_]
    frame_support: npt.NDArray[np.int64]
    model_dim: int


def _weighted_lp_solve(
    sp: npt.NDArray[np.float64],
    fs: float,
    weight: npt.NDArray[np.float64],
    *,
    preemph_hz: float = _PREEMPH_HZ,
    frame_len_s: float = _FRAME_LEN_S,
    frame_hop_s: float = _FRAME_HOP_S,
) -> WeightedLpResult:
    """Per-frame weighted-covariance AR estimate, inverse filter, de-emphasis.

    ``weight`` is a length-``n_samples`` per-sample analysis weight aligned with
    ``sp`` -- the method's only degree of freedom. Runs at the signal's native ``fs``
    (GIF7): the order ``nar = ceil(fs/1000)`` and the frame grid are formulas in ``fs``.
    """
    sp = np.asarray(sp, dtype=np.float64)
    weight = np.asarray(weight, dtype=np.float64)
    nsp = sp.size
    nar = int(np.ceil(fs / 1000.0))  # one pole per 1000 Hz (rule 1, from source)

    # Analysis-frame grid (reference: tstart = (nar+1):inc:(nsp-wl-1), 1-based).
    wl = int(matlab_round(fs * frame_len_s))
    inc = int(matlab_round(fs * frame_hop_s))
    tstart_1 = np.arange(nar + 1, nsp - wl, inc, dtype=np.int64)  # 1-based frame starts
    starts0 = tstart_1 - 1  # 0-based

    # Pre-emphasis: estimate the AR on the pre-emphasised signal, power preserved.
    b = np.array([1.0, -np.exp(-2 * np.pi * preemph_hz / fs)])
    a_scale = float(np.sqrt(1.0 / np.sum(b**2)))
    sp_pre = scipy.signal.lfilter(b, [a_scale], sp)

    ar = np.empty((starts0.size, nar + 1), dtype=np.float64)
    dc = np.empty(starts0.size, dtype=np.float64)
    frame_valid = np.empty(starts0.size, dtype=np.bool_)
    frame_support = np.empty(starts0.size, dtype=np.int64)
    model_dim = nar + 1  # nar lags + 1 DC term
    for f, t0 in enumerate(starts0):
        lo = int(t0) - nar  # include nar samples of history before the frame start
        hi = int(t0) + wl + 1  # predicted interval [t0, t0+wl] inclusive -> half-open
        x_frame = sp_pre[lo:hi]
        w_frame = weight[lo:hi]
        # GIF1: the reference weights error by W^2, so pass the weight squared. For a
        # 0/1 mask (cp) w**2 == w (a no-op); the continuous-weight methods (AME,
        # Gaussian) genuinely differ -- squared uniformly here for all of them.
        res = lpc_covar(x_frame, nar, weights=w_frame**2, dc_offset=True)
        ar[f] = res.a
        dc[f] = res.dc if res.dc is not None else 0.0
        # GIF5 (Option B): a frame is invalid iff its nonzero-weight support over the
        # predicted samples is below the model dimension (nar lags + 1 DC = nar+1). The
        # cheap sufficient rank check: count nonzero weights. lpc_covar still returned
        # the min-norm solution above -- the flow stays finite.
        support = int(np.count_nonzero(w_frame[nar:]))
        frame_support[f] = support
        frame_valid[f] = support >= model_dim

    # Inverse-filter the ORIGINAL signal with the per-frame AR and DC, then de-emphasise
    # (reference: uu = lpcifilt(sp, ar, T, dc); u = filter(a, b, uu)).
    uu = inverse_filter_frames(sp, ar, starts0, dc=dc)
    u = scipy.signal.lfilter([a_scale], b, uu)

    return WeightedLpResult(
        u=u,
        uu=uu,
        weight=weight,
        frame_starts=starts0,
        frame_valid=frame_valid,
        frame_support=frame_support,
        model_dim=model_dim,
    )


def invalid_cycle_mask(
    gci: npt.NDArray[np.int64], result: WeightedLpResult
) -> npt.NDArray[np.bool_]:
    """Per-cycle GIF5 mask: which cycles a rank-deficient frame invalidates.

    Returns a bool array aligned 1:1 with ``gci`` (row ``i`` is the cycle beginning at
    ``gci[i]``, spanning ``[gci[i], gci[i+1])`` -- the last cycle to the signal end). A
    cycle is invalidated (``True``) iff its span **overlaps** an invalid frame's
    inverse-filter output span ``[frame_starts[k], frame_starts[k+1])``: the ``uu`` flow
    over that cycle is then (partly) the minimum-norm solution of a rank-deficient
    frame, so its per-cycle source features are uncomputable.

    Overlap (not GCI-membership) is the rule because the flow, not the GCI, is what a
    cycle's features are measured from: a cycle straddling the boundary of an invalid
    frame draws corrupted flow and must be masked.

    This is the **local ``uu`` extent** -- the cycles whose *derivative* flow is
    directly rank-deficient. It is NOT the mask the feature composition uses: the
    features read ``u = de-emphasise(uu)``, whose IIR carries the divergence forward to
    the signal end (GIF8), so `voicekit.features.apply_invalid_frame_mask` masks the
    wider **forward** extent (every cycle from the first invalid frame onward). Use this
    primitive only for a ``uu``-only consumer; use the feature-layer composition for
    anything reading ``u``. See REFERENCE_NOTES GIF5/GIF8.
    """
    gci = np.atleast_1d(np.asarray(gci, dtype=np.int64))
    n = result.uu.size
    starts = result.frame_starts
    cyc_lo = gci
    cyc_hi = np.append(gci[1:], n) if gci.size else gci
    mask = np.zeros(gci.size, dtype=np.bool_)
    for k in np.flatnonzero(~result.frame_valid):
        lo = int(starts[k])
        hi = int(starts[k + 1]) if k + 1 < starts.size else n
        mask |= (cyc_lo < hi) & (cyc_hi > lo)  # span overlap
    return mask
