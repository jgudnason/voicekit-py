"""Per-cycle voice-source feature container."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class VoiceFeatures:
    """Per-cycle voice-source features, one row per glottal cycle.

    Aligned 1:1 with `GciResult`: row ``i`` is the cycle beginning at ``gci[i]``,
    so ``VoiceFeatures`` rows, ``gci`` and ``goi`` share one indexing contract.
    This is the reference's ``len(gci)+1`` output with its left-edge non-cycle
    (signal-start-to-first-closure) dropped; the right edge (last closure to
    signal end) is kept as the final row, matching ``goi[-1]``.

    All feature fields are ``float`` so an uncomputable cycle is ``NaN`` rather
    than a poison value (a consumer checks ``np.isnan`` before use); ``framek``
    (cycle-centre sample) and ``vuv`` (voiced flag) are always defined.
    """

    f0: npt.NDArray[np.float64]  # fundamental frequency (Hz)
    framek: npt.NDArray[np.int64]  # 0-based cycle-centre sample index
    vuv: npt.NDArray[np.bool_]  # voiced flag
    mfdr: npt.NDArray[np.float64]  # maximum flow declination rate
    cq: npt.NDArray[np.float64]  # closed quotient
    pa: npt.NDArray[np.float64]  # pulse amplitude
    naq: npt.NDArray[np.float64]  # normalized amplitude quotient
    h1h2: npt.NDArray[np.float64]  # H1-H2 level difference
    hrf: npt.NDArray[np.float64]  # harmonic richness factor
    qoq: npt.NDArray[np.float64]  # quasi-open quotient
