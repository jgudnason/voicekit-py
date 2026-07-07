"""Voice-source feature extraction -- the public entry point.

Wires the feature groups over the shared per-cycle framework and returns the
`VoiceFeatures` container. Built up as the groups land; this stage populates the
framework fields (``f0``, ``framek``, ``vuv``) and leaves the rest ``NaN``.
"""

import numpy as np
import numpy.typing as npt

from voicekit.features.config import FeaturesConfig
from voicekit.features.flow import flow_statistics
from voicekit.features.framework import cycle_framework
from voicekit.features.result import VoiceFeatures
from voicekit.features.timing import timing_statistics


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
    ``gci``. (This build populates the framework, flow-statistic and timing
    fields; the spectral fields land with their group and are ``NaN`` for now.)
    """
    cfg = config if config is not None else FeaturesConfig()
    u = np.asarray(u, dtype=np.float64)
    uu = np.asarray(uu, dtype=np.float64)
    gci = np.atleast_1d(np.asarray(gci)).astype(np.int64)
    n = gci.size

    # The reference works 1-based; our gci is 0-based (GciResult convention).
    gci_1based = gci + 1
    raw_f0, raw_framek, raw_vuv = cycle_framework(gci_1based, u.size, fs, cfg)
    raw_mfdr, raw_pa, raw_naq = flow_statistics(u, uu, gci_1based, fs, cfg)
    raw_cq, raw_qoq = timing_statistics(u, gci_1based, fs, cfg)

    # Shape (d): drop the left-edge non-cycle (raw[0]); rows 1: align to gci.
    unfilled = np.full(n, np.nan)
    return VoiceFeatures(
        f0=raw_f0[1:],
        framek=(raw_framek[1:] - 1).astype(np.int64),  # 1-based -> 0-based
        vuv=raw_vuv[1:] == 1.0,
        mfdr=raw_mfdr[1:],
        pa=raw_pa[1:],
        naq=raw_naq[1:],
        cq=raw_cq[1:],
        qoq=raw_qoq[1:],
        h1h2=unfilled.copy(),
        hrf=unfilled.copy(),
    )
