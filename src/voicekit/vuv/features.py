"""Atal-Rabiner per-frame voicing features: Nz, Es, C1, alp1, Ep.

Reproduces the feature definitions of the reference VUV feature extractor (Jon
Gudnason 2004; after Atal & Rabiner 1976) -- **the definitions, reproduced from
the formulas, not ported**. This is the FEATURE SET only: it emits the per-frame
feature matrix, no voicing label, no threshold, no decision.

The features ride the locked `VoicingGrid` (one framing for all five). Two of the
five are direct frame statistics (``Nz``, ``C1``); the other three come from a
single **DC-offset** covariance-LPC per frame (``alp1``, ``Es``, ``Ep`` share one
`lpc_covar(..., dc_offset=True)` call, matching the reference's three-output
``[ar,e,dc]=lpccovar(...)`` — reading its coefficients, signal energy, and
residual energy).

Reference quirks are reproduced exactly and quarantined behind the (deferred)
VUV1 pre-gate -- see REFERENCE_NOTES "Step 7 (VUV)":
  - a zero-energy frame yields ``Es = -inf`` and ``Ep = NaN``, and a silent
    frame yields ``C1 = NaN`` -- a dropped-guard artifact, not a principled
    degeneracy: the reference zeroed (``eps=0``) the guards the paper mandates
    (eps=1e-5 in Eq. (2), 1e-6 in Eq. (4)), so the paper's silent frames get a
    finite floor where ours reproduce the MATLAB's ``-inf``/``NaN``
    (VUV1/VUV10);
  - ``C1``'s boundary term reaches one sample *before* the frame and is broadcast
    across the N-1 products (it enters N-1 times), making ``C1`` unbounded above
    -- reproduced, not corrected (VUV7/VUV8; the paper's Eq. (3) enters it once,
    see VUV10 and docs/vuv_c1_decision.md);
  - ``Nz`` takes the sign as ``>= 0`` (zero counts non-negative);
  - the history-less first frame (start 0) is undefined and routed to the same
    pre-gate path as silence -- never computed from ``s[-1]`` (the signal tail).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from voicekit.lpc import lpc_covar
from voicekit.signal import Signal
from voicekit.vuv.grid import VoicingGrid


@dataclass(frozen=True)
class VuvFeaturesConfig:
    """Config for the VUV feature layer -- features only.

    Distinct from the deferred *threshold* config (VUV1's ``VuvConfig``): this
    carries only the framing (`VoicingGrid`) and the covariance-LPC order
    (``nar``; 16 is the reference caller's convention -- the paper itself says
    p = 12 "typically"; see REFERENCE_NOTES VUV10).
    """

    grid: VoicingGrid = field(default_factory=VoicingGrid)
    lpc_order: int = 16


@dataclass(frozen=True)
class FrameFeatures:
    """Per-frame Atal-Rabiner feature matrix; one row per `VoicingGrid` frame.

    **Not a voicing track** -- no labels. Degenerate frames (silence; the
    history-less first frame) carry the reference's reproduced ``-inf``/``NaN``
    (for silence, a dropped-guard artifact -- see the module docstring and
    VUV1/VUV10), quarantined behind the deferred VUV1 pre-gate: a consumer must
    check ``np.isnan``/``np.isinf`` before use. ``frame_centers`` are 0-based
    sample positions from `VoicingGrid.frame_centers`.
    """

    nz: npt.NDArray[np.float64]
    es: npt.NDArray[np.float64]
    c1: npt.NDArray[np.float64]
    alp1: npt.NDArray[np.float64]
    ep: npt.NDArray[np.float64]
    frame_centers: npt.NDArray[np.float64]

    @property
    def n_frames(self) -> int:
        return len(self.nz)


def frame_features_at(
    s: npt.NDArray[np.float64], start: int, frame_len: int, nar: int
) -> tuple[float, float, float, float, float]:
    """The five features ``(Nz, Es, C1, alp1, Ep)`` for the frame at ``start``.

    The single per-frame path, shared by `extract_frame_features` (over VoicingGrid
    starts) and the parity test (over the reference's own window starts) -- so the
    MATLAB parity exercises the same code the module runs, not a copy of it.
    """
    frame = s[start : start + frame_len]
    # Nz: history-free, defined for every frame. Sign via >= 0 (reproduce),
    # transitions of the sign sequence summed.
    nz = float(np.sum(np.abs(np.diff((frame >= 0.0).astype(np.int64)))))

    if start < nar:
        # No nar-sample covariance history (and no s[start-1] for C1's s0).
        # Undefined -> routed to the same pre-gate path as silence. Guarding here
        # is what prevents s[start-1] == s[-1] silently wrapping to the signal
        # tail and computing a spurious finite C1 (VUV pin).
        return nz, np.nan, np.nan, np.nan, np.nan

    # One covariance LPC over the pre-frame-history window reproduces v_lpccovar
    # (predict the frame w[nar:] from the history w[:nar]). dc_offset=True matches
    # the reference's THREE-output call `[ar,e,dc]=lpccovar(...)`, fitting the AR
    # about a jointly-fitted DC level: alp1 (ar) and Ep (residual energy) come
    # from that fit. Es reads signal_energy, which is DC-independent (unchanged).
    w = s[start - nar : start + frame_len]
    res = lpc_covar(w, nar, dc_offset=True)
    sig_e = res.signal_energy
    assert sig_e is not None  # covariance solver always sets it (commit 1)

    # Reproduce the disabled-eps degeneracies (log10(0) -> -inf, 0/0 -> NaN)
    # silently; these are the intended reference values, not numerical accidents.
    with np.errstate(divide="ignore", invalid="ignore"):
        es = 10.0 * np.log10(sig_e / frame_len)  # eps disabled: 0 -> -inf
        ep = es - 10.0 * np.log10(res.error / frame_len)
        # C1: lag-1 with the boundary sample s0 = s[start-1], reaching one sample
        # before the frame. Reproduced quirk (VUV7): the NUMERATOR boundary term
        # frame[0]*s0 is broadcast across the N-1 products (MATLAB vector+scalar)
        # so it enters N-1 times, while the DENOMINATOR carries s0 once (one
        # element of [s0, frame[:-1]]). That asymmetry is why C1 is unbounded above
        # (VUV8) -- do NOT collapse it to add-once. Silent frame -> 0/0 = NaN.
        s0 = s[start - 1]
        ssq = float(frame @ frame)
        shifted = np.concatenate(([s0], frame[:-1]))
        num = float(np.sum(frame[1:] * frame[:-1] + frame[0] * s0))
        c1 = num / np.sqrt(ssq * float(shifted @ shifted))

    return nz, float(es), float(c1), float(res.a[1]), float(ep)


def extract_frame_features(
    signal: Signal, config: VuvFeaturesConfig | None = None
) -> FrameFeatures:
    """Compute the five per-frame features over ``signal`` on the VoicingGrid."""
    cfg = config if config is not None else VuvFeaturesConfig()
    s = np.asarray(signal.samples, dtype=np.float64)
    fs = float(signal.fs)
    nar = cfg.lpc_order
    frame_len = cfg.grid.frame_len(fs)
    hop = cfg.grid.hop(fs)
    centers = cfg.grid.frame_centers(len(s), fs)
    n = len(centers)

    nz: npt.NDArray[np.float64] = np.empty(n, dtype=np.float64)
    es: npt.NDArray[np.float64] = np.empty(n, dtype=np.float64)
    c1: npt.NDArray[np.float64] = np.empty(n, dtype=np.float64)
    alp1: npt.NDArray[np.float64] = np.empty(n, dtype=np.float64)
    ep: npt.NDArray[np.float64] = np.empty(n, dtype=np.float64)

    for k in range(n):
        nz[k], es[k], c1[k], alp1[k], ep[k] = frame_features_at(s, k * hop, frame_len, nar)

    return FrameFeatures(nz=nz, es=es, c1=c1, alp1=alp1, ep=ep, frame_centers=centers)
