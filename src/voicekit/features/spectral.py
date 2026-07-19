"""Spectral voice features: H1-H2 and HRF (harmonic richness factor).

Per-cycle harmonic analysis of the glottal flow. Over each cycle the magnitude
spectrum ``oa = abs(fft(useg))/T`` is taken (``useg = u(nn)/fs``, the same segment
as every other group; no window), and the first ``floor(harmonic_limit/f0)``
harmonics are read **directly from integer FFT bins** -- bin ``k`` is treated as
harmonic ``k`` (H1 = bin 1, H2 = bin 2), with no interpolation or peak search.
Both features are ratios relative to H1, in dB, so the ``/T`` and the absolute
spectrum scaling cancel:

    h1h2 = 20*log10(A1/A2)                 first-harmonic minus second (spectral tilt)
    hrf  = 10*log10(sum_{k>=2} (Ak/A1)^2)  harmonic power above H1, relative to H1

Two reference oddities are reproduced here (faithfully, golden parity is the only
gate); see REFERENCE_NOTES.md "Feature observations":

* **V3 (crossed assignment).** The reference's caller stores the two outputs under
  swapped names: the array it calls ``h1h2`` receives HRF and the array it calls
  ``hrf`` receives H1-H2. The capture saved those swapped arrays, so parity
  requires the same swap. `spectral_params` returns the two values **correctly
  named**; `spectral_statistics` performs the swap once, at the assignment, so the
  crossing is visible at the swap site rather than hidden. Consequently
  ``VoiceFeatures.h1h2`` holds the reference's HRF and ``VoiceFeatures.hrf`` holds
  H1-H2 -- reproduced for parity; the correction is simply to uncross.
* **V4 (harmonic bins off by the T+2 length).** ``useg`` is ``T+2`` samples long
  but harmonics are read at integer bins as if it were ``T``-periodic, so harmonic
  ``k`` (at ``k*fs/T``) actually sits near bin ``k*(T+2)/T``, not bin ``k`` -- the
  same ``T = len(nn)-2`` convention as V1, resurfacing in the bin indexing.

When too few harmonics fall below ``harmonic_limit`` (``floor(harmonic_limit/f0)
<= 1``, i.e. very high f0) the reference returns a literal ``0`` for both -- not
NaN; no fixture cycle reaches it (REFERENCE_NOTES.md "Coverage gaps" C5).

Reference: the reference feature-extraction pipeline (``specParam``, "As implemented by
Yu-Ren", and its caller); reimplemented from the source, not ported.
"""

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from voicekit.features.config import FeaturesConfig
from voicekit.features.framework import CyclePrep


def spectral_params(
    useg: npt.NDArray[np.float64], period: int, fs: float, harmonic_limit: float
) -> tuple[float, float]:
    """Return **correctly named** ``(h1h2, hrf)`` in dB for one cycle segment.

    ``h1h2`` is the true H1-H2 (``20*log10(A1/A2)``) and ``hrf`` the true harmonic
    richness factor (``10*log10`` of the summed higher-harmonic power relative to
    H1). Harmonics are read from integer FFT bins 1..``floor(harmonic_limit/f0)``
    (see V3/V4 in the module docstring). Returns ``(0.0, 0.0)`` when too few
    harmonics fall below ``harmonic_limit`` (the reference's degenerate return --
    a literal zero, not NaN; REFERENCE_NOTES.md C5).

    Note: the caller (`spectral_statistics`) stores these under swapped names to
    reproduce the reference (V3); this function itself is not crossed.
    """
    f0 = fs / period
    oa = np.abs(np.fft.fft(useg)) / period  # /period cancels in the ratios below
    number_partials = int(np.floor(harmonic_limit / f0))
    if number_partials <= 1:
        return 0.0, 0.0  # too few harmonics below harmonic_limit (high f0); reference C5

    partial_amplitudes = oa[1 : number_partials + 1]  # bins 1..np = harmonics 1..np
    amplitudes_db = 20.0 * np.log10(partial_amplitudes / partial_amplitudes[0])
    h1h2 = -amplitudes_db[1]  # H1 - H2
    hrf = 10.0 * np.log10(np.sum(10.0 ** (amplitudes_db[1:] / 10.0)))
    return float(h1h2), float(hrf)


def spectral_statistics(
    preps: Sequence[CyclePrep], fs: float, config: FeaturesConfig | None = None
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Raw per-cycle ``(h1h2, hrf)`` over the prepared cycles.

    Reads the UNSHIFTED ``useg`` and ``period`` from each `CyclePrep`. Returns arrays
    matching the reference's **stored** arrays, i.e. **crossed** (V3): the returned
    ``h1h2`` holds the reference's HRF and the returned ``hrf`` holds H1-H2. Parity
    with the capture holds because both are swapped the same way.
    """
    cfg = config if config is not None else FeaturesConfig()

    h1h2 = np.zeros(len(preps))
    hrf = np.zeros(len(preps))
    for ig, p in enumerate(preps):
        h1h2_real, hrf_real = spectral_params(p.useg, p.period, fs, cfg.harmonic_limit_hz)
        # V3: the reference stores the two outputs crossed (REFERENCE_NOTES.md V3).
        # The array named h1h2 receives HRF; the array named hrf receives H1-H2.
        h1h2[ig] = hrf_real
        hrf[ig] = h1h2_real
    return h1h2, hrf
