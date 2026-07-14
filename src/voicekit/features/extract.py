"""Voice-source feature extraction -- the public entry point.

Wires the feature groups over one shared per-cycle prep (`prepare_cycles`) and returns
the `VoiceFeatures` container. The signal groups (flow, timing, spectral) consume the
prep so ``useg``/``uuseg``, the DC-shift, and ``O1`` are computed once; the seam then
applies the ``O1==0`` mask over the five timing/flow features.
"""

import numpy as np
import numpy.typing as npt

from voicekit.features.config import FeaturesConfig
from voicekit.features.flow import flow_statistics
from voicekit.features.framework import cycle_framework
from voicekit.features.prep import prepare_cycles
from voicekit.features.result import VoiceFeatures
from voicekit.features.spectral import spectral_statistics
from voicekit.features.timing import timing_statistics

# Features zeroed on a no-open-phase (O1==0) cycle, per the reference's degenerate
# branch. f0/framek/vuv/h1h2/hrf are intentionally NOT in this set.
_O1_ZERO_SUBSET = ("cq", "qoq", "mfdr", "pa", "naq")


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
    raw_f0, raw_framek, raw_vuv = cycle_framework(gci, u.size, fs, cfg)
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
        vuv=raw_vuv[1:] == 1.0,
        mfdr=raw["mfdr"][1:],
        pa=raw["pa"][1:],
        naq=raw["naq"][1:],
        cq=raw["cq"][1:],
        qoq=raw["qoq"][1:],
        h1h2=raw_h1h2[1:],  # crossed (V3): holds the reference's HRF
        hrf=raw_hrf[1:],  # crossed (V3): holds H1-H2
    )
