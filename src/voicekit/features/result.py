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

    ``framek`` is 0-based, the mirror of the 0-based ``gci`` input: everything
    crossing the public boundary is 0-based, and the reference's 1-based cycle
    frame is confined to ``iter_cycle_segments``. framek is *computed* 1-based
    there (centre of the 1-based interval) and converted back once on output, so
    the input ``+1`` and this output ``-1`` act on different quantities (gci in,
    framek out) and are each independently load-bearing -- one convention applied
    at both ends of the boundary, not a cancelling pair.

    .. warning::
       ``h1h2`` and ``hrf`` are **crossed**: the reference stores its two spectral
       outputs under swapped names, and the port reproduces that for golden parity.
       So ``h1h2`` actually holds the **harmonic richness factor** and ``hrf`` holds
       the **H1-H2 level difference** -- the opposite of their names. This is
       reproduced, not corrected; the correction is to uncross the two. See
       REFERENCE_NOTES.md "Feature observations" V3.
    """

    f0: npt.NDArray[np.float64]  # fundamental frequency (Hz)
    framek: npt.NDArray[np.int64]  # 0-based cycle-centre sample index
    vuv: npt.NDArray[np.bool_]  # voiced flag
    mfdr: npt.NDArray[np.float64]  # maximum flow declination rate
    cq: npt.NDArray[np.float64]  # closed quotient
    pa: npt.NDArray[np.float64]  # pulse amplitude
    naq: npt.NDArray[np.float64]  # normalized amplitude quotient
    h1h2: npt.NDArray[np.float64]  # CROSSED (V3): actually holds HRF, not H1-H2
    hrf: npt.NDArray[np.float64]  # CROSSED (V3): actually holds H1-H2, not HRF
    qoq: npt.NDArray[np.float64]  # quasi-open quotient
