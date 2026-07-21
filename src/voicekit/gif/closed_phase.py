"""Closed-phase weighted-LP glottal inverse filtering (the ``cp`` method).

Reproduces the reference weighted-LP solve wrapper's closed-phase path: estimate
a per-frame AR model on the pre-emphasised signal under the closed-phase 0/1
weight (GIF2 mask), inverse-filter the original signal with those per-frame
coefficients, and de-emphasise -- yielding the glottal flow ``uu`` and its
integrated form ``u``. The full-frame solve with a 0/1 weight (not an
interval-restricted solve) is GIF2's locked design; the ``W^2`` weight convention
is GIF1.

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
import scipy.signal

from voicekit._matlab_compat import matlab_round
from voicekit.gif.config import ClosedPhaseConfig
from voicekit.gif.goi_selection import reconstruct_gois
from voicekit.gif.mask import closed_phase_weight
from voicekit.lpc.covariance import lpc_covar
from voicekit.lpc.frames import inverse_filter_frames


@dataclass(frozen=True)
class ClosedPhaseResult:
    """Output of the closed-phase weighter.

    ``uu`` is the glottal flow derivative (inverse-filtered signal); ``u`` its
    de-emphasised (integrated) form -- both length ``n_samples``, numerically
    pure (never NaN). ``weight`` is the 0/1 closed-phase analysis weight, and
    ``goi`` the reconstructed per-cycle openings the weight was built from
    (exposed for inspection / golden-master).

    ``frame_starts`` are the 0-based analysis-frame start samples; ``frame_valid``
    is the per-frame GIF5 validity flag (``False`` where the frame's nonzero-weight
    support fell below the model dimension, so its AR is the minimum-norm solution
    of a rank-deficient system). The per-frame flag is turned into per-cycle NaN
    downstream, not here.
    """

    u: npt.NDArray[np.float64]
    uu: npt.NDArray[np.float64]
    weight: npt.NDArray[np.float64]
    goi: npt.NDArray[np.int64]
    frame_starts: npt.NDArray[np.int64]
    frame_valid: npt.NDArray[np.bool_]


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

    nar = int(np.ceil(fs / 1000.0))  # one pole per 1000 Hz (rule 1, from source)

    # GOI-selection reconstruction (GIF6) -> the gap-free openings the mask needs.
    goi = reconstruct_gois(gci, goi_candidates, cfg.apop)
    weight = closed_phase_weight(gci, goi, nsp, fs, cfg)

    # Analysis-frame grid (reference: tstart = (nar+1):inc:(nsp-wl-1), 1-based).
    wl = int(matlab_round(fs * cfg.frame_len_s))
    inc = int(matlab_round(fs * cfg.frame_hop_s))
    tstart_1 = np.arange(nar + 1, nsp - wl, inc, dtype=np.int64)  # 1-based frame starts
    starts0 = tstart_1 - 1  # 0-based

    # Pre-emphasis: estimate the AR on the pre-emphasised signal, power preserved.
    b = np.array([1.0, -np.exp(-2 * np.pi * cfg.preemph_hz / fs)])
    a_scale = float(np.sqrt(1.0 / np.sum(b**2)))
    sp_pre = scipy.signal.lfilter(b, [a_scale], sp)

    ar = np.empty((starts0.size, nar + 1), dtype=np.float64)
    dc = np.empty(starts0.size, dtype=np.float64)
    frame_valid = np.empty(starts0.size, dtype=np.bool_)
    for f, t0 in enumerate(starts0):
        lo = int(t0) - nar  # include nar samples of history before the frame start
        hi = int(t0) + wl + 1  # predicted interval [t0, t0+wl] inclusive -> half-open
        x_frame = sp_pre[lo:hi]
        w_frame = weight[lo:hi]
        # GIF1: the reference weights error by W^2, so pass the mask squared. For a
        # 0/1 mask w**2 == w (a no-op here), but the method layer squares uniformly
        # for the continuous-weight methods (AME, Gaussian) that share this seam.
        res = lpc_covar(x_frame, nar, weights=w_frame**2, dc_offset=True)
        ar[f] = res.a
        dc[f] = res.dc if res.dc is not None else 0.0
        # GIF5 (Option B): a frame is invalid iff its nonzero-weight support over
        # the predicted samples is below the model dimension (nar lags + 1 DC =
        # nar+1). The cheap sufficient rank check: count nonzero weights. lpc_covar
        # still returned the min-norm solution above -- the flow stays finite.
        support = int(np.count_nonzero(w_frame[nar:]))
        frame_valid[f] = support >= nar + 1

    # Inverse-filter the ORIGINAL signal with the per-frame AR and DC, then
    # de-emphasise (reference: uu = lpcifilt(sp, ar, T, dc); u = filter(a, b, uu)).
    uu = inverse_filter_frames(sp, ar, starts0, dc=dc)
    u = scipy.signal.lfilter([a_scale], b, uu)

    return ClosedPhaseResult(
        u=u, uu=uu, weight=weight, goi=goi, frame_starts=starts0, frame_valid=frame_valid
    )


def invalid_cycle_mask(
    gci: npt.NDArray[np.int64], result: ClosedPhaseResult
) -> npt.NDArray[np.bool_]:
    """Per-cycle GIF5 mask: which cycles a rank-deficient frame invalidates.

    Returns a bool array aligned 1:1 with ``gci`` (row ``i`` is the cycle
    beginning at ``gci[i]``, spanning ``[gci[i], gci[i+1])`` -- the last cycle to
    the signal end). A cycle is invalidated (``True``) iff its span **overlaps** an
    invalid frame's inverse-filter output span ``[frame_starts[k], frame_starts[k+1])``:
    the ``uu`` flow over that cycle is then (partly) the minimum-norm solution of a
    rank-deficient frame, so its per-cycle source features are uncomputable.

    Overlap (not GCI-membership) is the rule because the flow, not the GCI, is what
    a cycle's features are measured from: a cycle straddling the boundary of an
    invalid frame draws corrupted flow and must be masked. This maps only the
    *directly* corrupted ``uu`` span; note that ``u``'s de-emphasis IIR smears the
    divergence forward (see the golden test), a forward taint this per-frame mask
    does not chase -- flagged in REFERENCE_NOTES GIF5, not silently absorbed here.
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
