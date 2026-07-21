"""Voice-source feature extraction -- the public entry point.

Wires the feature groups over one shared per-cycle prep (`prepare_cycles`) and returns
the `VoiceFeatures` container. The signal groups (flow, timing, spectral) consume the
prep so ``useg``/``uuseg``, the DC-shift, and ``O1`` are computed once; the seam then
applies the ``O1==0`` mask over the five timing/flow features.

`apply_voicing_mask` is the step-7 bridge: an **explicit, opt-in** second
`apply_cycle_mask` call that nans the source features of cycles the voicing
detector called non-voiced. `extract_voice_features` stays track-free and
parity-preserving -- masking is a composition step the caller applies, never a
default, mirroring `voicekit.vuv.condition`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt

from voicekit.features.config import FeaturesConfig
from voicekit.features.flow import flow_statistics
from voicekit.features.framework import cycle_framework
from voicekit.features.prep import prepare_cycles
from voicekit.features.result import VoiceFeatures
from voicekit.features.spectral import spectral_statistics
from voicekit.features.timing import timing_statistics

if TYPE_CHECKING:  # annotation only -- keeps the feature layer runtime-independent of vuv/gif
    from voicekit.gif.closed_phase import ClosedPhaseResult
    from voicekit.vuv.decision import VoicingTrack

# Features zeroed on a no-open-phase (O1==0) cycle, per the reference's degenerate
# branch. f0/framek/frame_len_ok/h1h2/hrf are intentionally NOT in this set.
_O1_ZERO_SUBSET = ("cq", "qoq", "mfdr", "pa", "naq")

# Features nan'd on a NON-VOICED cycle -- the eight *source measurements*, all
# meaningless when there is no glottal source. Larger than _O1_ZERO_SUBSET (which
# is a real cycle with a degenerate open phase, so f0/spectrum survive): here the
# condition is "no real cycle at all", so f0 (no phonation) and the spectral pair
# (no harmonic structure) go too. framek (location) and frame_len_ok (geometry
# flag) are STRUCTURAL -- defined regardless of source reality -- and are kept.
_VOICING_MASK_SUBSET = ("f0", "cq", "qoq", "mfdr", "pa", "naq", "h1h2", "hrf")


def apply_cycle_mask(
    raw: dict[str, npt.NDArray[np.float64]],
    mask: npt.NDArray[np.bool_],
    subset: tuple[str, ...],
    value: float,
) -> None:
    """Assign ``value`` to ``raw[name][mask]`` for each ``name`` in ``subset``, in place.

    A reusable ``(mask, subset, value)`` step: the ``O1==0`` masking is one call, and
    step 7's voiced/unvoiced masking will be a second one over its own subset -- no
    restructuring, because this is not an ``if O1==0`` branch. ``np.where`` is correct
    here because it **selects** between ``value`` and the existing array rather than
    arithmetically combining them; the ``0 * nan`` hazard is avoided by never
    multiplying by the mask (index-assignment would be equally safe).
    """
    for name in subset:
        raw[name] = np.where(mask, value, raw[name])


def apply_voicing_mask(
    feats: VoiceFeatures,
    gci: npt.NDArray[np.int64],
    track: VoicingTrack,
) -> tuple[VoiceFeatures, npt.NDArray[np.str_]]:
    """Nan the source features of cycles the voicing detector called non-voiced.

    The derived per-cycle mask (step-7 architecture gate): each cycle inherits
    the verdict of the frame its GCI projects to. ``feats`` is one row per cycle,
    aligned 1:1 with ``gci`` (row ``i`` begins at ``gci[i]``); ``track`` is a
    `VoicingTrack` from `detect_voicing`. Returns a **new** `VoiceFeatures` with
    the eight source measurements (`_VOICING_MASK_SUBSET`) set to ``NaN`` on every
    non-voiced cycle, and a per-cycle **reason** array (``"voiced"`` / ``"floor"``
    / ``"aperiodic"`` / ``"undefined"``) so the masking is observable, not just a
    silent ``NaN``.

    **Opt-in, never a default.** `extract_voice_features` is track-free and
    parity-preserving; this is the composition step a caller applies when it
    wants voiced-only source features, like `voicekit.vuv.condition`.

    **Lookup.** GCI -> frame via `VoicingTrack.frame_index` (nearest-centre
    `project`, the single-sourced formula) -- no second copy of the projection
    arithmetic.

    **Value, and composition with the O1==0 mask.** ``NaN``, not ``0.0``: a
    non-voiced cycle is *uncomputable* (no glottal source), which has no reference
    value -- unlike the O1==0 degenerate branch, whose ``0.0`` is the reference's
    own defined output. The two masks compose; on a cycle that is both O1==0
    (already ``0.0``) and non-voiced, **``NaN`` wins**, which is correct: no
    source means no value, defined-degenerate or not.

    **D2 propagation (VUV17), inherited visibly.** The detector cannot tell D2's
    voiced frication from genuine aspiration -- that indistinguishability *is* the
    VUV11 limit -- so voiced frication reads non-voiced and its (real, computable)
    cycles are masked here with ``reason == "aperiodic"``. That is a documented
    step-7 limit inherited into step-6 output, made **observable** by the reason
    channel (``"aperiodic"``, not ``"floor"``): a caller who knows the material is
    voiced frication can recover those cycles. Masked-by-default is the safe
    choice (a visible ``NaN`` beats finite garbage from a spurious noise GCI); the
    reason is what keeps the limit from being silent.
    """
    gci = np.atleast_1d(np.asarray(gci)).astype(np.int64)
    reason = np.empty(len(gci), dtype="<U9")
    for i, g in enumerate(gci):
        k = track.frame_index(int(g))
        if track.voiced[k]:
            reason[i] = "voiced"
        elif track.floor_gated[k]:  # silence takes precedence over the 0/0 it also causes
            reason[i] = "floor"
        elif track.undefined[k]:
            reason[i] = "undefined"
        else:
            reason[i] = "aperiodic"

    masked = reason != "voiced"
    raw = {name: getattr(feats, name).copy() for name in _VOICING_MASK_SUBSET}
    apply_cycle_mask(raw, masked, _VOICING_MASK_SUBSET, np.nan)
    return replace(feats, **raw), reason


def apply_closed_phase_mask(
    feats: VoiceFeatures,
    gci: npt.NDArray[np.int64],
    result: ClosedPhaseResult,
) -> tuple[VoiceFeatures, npt.NDArray[np.str_]]:
    """Nan the source features of cycles a rank-deficient closed-phase frame corrupts.

    Completes GIF5: the weighter's per-frame validity flag becomes per-cycle NaN
    here, via the same `apply_cycle_mask` seam (value ``NaN``) VUV and O1==0 use.

    **Coverage is the forward smear, and that is correctness, not pessimism.** The
    feature groups read the flow ``u`` (``prepare_cycles``: ``useg = u/fs``; the
    spectral and amplitude features are ``u``-derived), and ``u = de-emphasise(uu)``
    is a causal IIR (5 Hz pole ~0.998) that carries a rank-deficient frame's ``uu``
    divergence FORWARD to the end of the signal (GIF8). So a rank-deficient frame
    invalidates not only its own cycles but **every cycle from its start onward** --
    each later cycle reads tainted ``u`` and would otherwise emit a finite-but-wrong
    feature the mask misses. There is no grounded sub-feature-magnitude cutoff (the
    pole decays slowly), so the full forward extent is masked. A ``reason`` array
    (``"valid"`` / ``"rank_deficient"``) keeps the masking observable.

    **Opt-in composition, and it composes with the VUV mask.** Like
    `apply_voicing_mask`, this is an explicit second `apply_cycle_mask` call, not a
    default; ``np.where`` **selects** ``NaN`` rather than multiplying, so applying
    both masks in either order NaNs the union of their cycles and neither clobbers
    the other's NaNs.
    """
    gci = np.atleast_1d(np.asarray(gci)).astype(np.int64)
    reason = np.full(gci.size, "valid", dtype="<U14")
    invalid = np.flatnonzero(~result.frame_valid)
    if invalid.size:
        # first corrupted u sample = the earliest rank-deficient frame's start;
        # the IIR taints u from there to the end. A cycle [gci[i], gci[i+1]) is
        # tainted iff it extends past that point (its end > first corrupted sample).
        first = int(result.frame_starts[int(invalid.min())])
        cyc_hi = np.append(gci[1:], result.uu.size) if gci.size else gci
        reason[cyc_hi > first] = "rank_deficient"
    masked = reason != "valid"
    raw = {name: getattr(feats, name).copy() for name in _VOICING_MASK_SUBSET}
    apply_cycle_mask(raw, masked, _VOICING_MASK_SUBSET, np.nan)
    return replace(feats, **raw), reason


def extract_voice_features(
    u: npt.NDArray[np.float64],
    uu: npt.NDArray[np.float64],
    fs: float,
    gci: npt.NDArray[np.int64],
    config: FeaturesConfig | None = None,
) -> VoiceFeatures:
    """Extract per-cycle voice-source features from the glottal flow.

    ``u`` is the glottal flow, ``uu`` its derivative, ``gci`` the 0-based closure
    instants (as `GciResult.gci`). Returns one row per glottal cycle, aligned to
    ``gci`` -- every feature group populated (framework, flow-statistic, timing,
    spectral).
    """
    cfg = config if config is not None else FeaturesConfig()
    u = np.asarray(u, dtype=np.float64)
    uu = np.asarray(uu, dtype=np.float64)
    gci = np.atleast_1d(np.asarray(gci)).astype(np.int64)

    # One shared per-cycle prep; the signal groups consume it (gci is 0-based -- the
    # single 0->1-based conversion lives in iter_cycle_segments, gciP=[1,gci+1,n]).
    preps = prepare_cycles(u, uu, gci, fs, cfg)
    raw_f0, raw_framek, raw_frame_len_ok = cycle_framework(gci, u.size, fs, cfg)
    raw_mfdr, raw_pa, raw_naq = flow_statistics(preps, fs)
    raw_cq, raw_qoq = timing_statistics(preps)
    raw_h1h2, raw_hrf = spectral_statistics(preps, fs, cfg)

    # O1==0 masking, once, over the five timing/flow features. The groups already leave
    # 0 on those cycles (the reference value), so this is a redundant safety net and the
    # reusable step step-7's voiced/unvoiced mask extends -- not an if-O1==0 branch.
    raw = {"cq": raw_cq, "qoq": raw_qoq, "mfdr": raw_mfdr, "pa": raw_pa, "naq": raw_naq}
    o1_zero = np.array([p.o1 == 0 for p in preps], dtype=bool)
    apply_cycle_mask(raw, o1_zero, _O1_ZERO_SUBSET, 0.0)

    # Shape (d): drop the left-edge non-cycle (raw[0]); rows 1: align to gci.
    return VoiceFeatures(
        f0=raw_f0[1:],
        framek=(raw_framek[1:] - 1).astype(np.int64),  # 1-based -> 0-based
        frame_len_ok=raw_frame_len_ok[1:] == 1.0,
        mfdr=raw["mfdr"][1:],
        pa=raw["pa"][1:],
        naq=raw["naq"][1:],
        cq=raw["cq"][1:],
        qoq=raw["qoq"][1:],
        h1h2=raw_h1h2[1:],  # crossed (V3): holds the reference's HRF
        hrf=raw_hrf[1:],  # crossed (V3): holds H1-H2
    )
