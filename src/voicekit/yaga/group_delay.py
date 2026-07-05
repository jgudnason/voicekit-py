"""Energy-weighted group delay and its zero-crossing GCI candidates.

The second front-end stage of YAGA GCI detection, parallel to the SWT
multiscale product: the two converge only at the dynamic-programming stage.
The energy-weighted group delay is a local energy *centroid* — at each
sample, the energy-weighted average offset within a short window. Where the
centroid crosses zero going negative marks a candidate glottal closure.

The centroid is formed as a ratio of two FIR filterings of the signal
energy ``u**2``: the numerator window is a Hamming window times an
antisymmetric linear ramp (zero at its centre), the denominator is the
plain Hamming window (local energy). The ratio is then smoothed by a short
Hamming low-pass. Negative-going zero crossings of the result, shifted to
the original-signal sample frame, are the candidates.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), "Estimation
    of Glottal Closure Instants in Voiced Speech using the DYPSA Algorithm",
    IEEE TASLP 15(1), 34-43 (the group-delay / phase-slope epoch extraction).

    Reference implementation: the ``xewgrdel`` subfunction of the
    VOICEBOX-bundled ``dypsagoi.m`` (and VOICEBOX ``zerocros`` for the
    interpolated crossing search). Reimplemented from the algorithm
    description, not ported.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import scipy.signal


@dataclass(frozen=True)
class GroupDelayConfig:
    """Window durations for `energy_weighted_group_delay` (seconds).

    Defaults follow the reference (`dy_gwlen`, `dy_fwlen`). Each duration is
    turned into an odd sample count by `odd_window_length`.
    """

    gw_len: float = 0.002  # energy-weighting (evaluation) window
    fw_len: float = 0.00045  # smoothing (low-pass) window


@dataclass(frozen=True)
class GroupDelayResult:
    """Outputs of the energy-weighted group delay stage.

    ``group_delay`` is the aligned, sign-flipped centroid used downstream
    (the reference's ``gdwav``): length ``len(u) - (gw - 1)``, with ``toff``
    leading zeros. ``centroid`` is the raw centroid before the sign flip and
    shift (the reference's ``gdwav_raw``). ``candidates`` are the fractional,
    0-based sample locations of the negative-going zero crossings in the
    original-signal frame, and ``slopes`` the centroid slope at each.
    """

    group_delay: npt.NDArray[np.float64]
    centroid: npt.NDArray[np.float64]
    candidates: npt.NDArray[np.float64]
    slopes: npt.NDArray[np.float64]
    toff: int


def odd_window_length(dur_s: float, fs: float) -> int:
    """Window length in samples forced odd: ``2*floor(dur*fs/2) + 1``."""
    return 2 * int(np.floor(dur_s * fs / 2)) + 1


def energy_weighted_group_delay(
    u: npt.NDArray[np.float64], fs: float, config: GroupDelayConfig | None = None
) -> GroupDelayResult:
    """Energy-weighted group delay of ``u`` and its negative-going zero crossings.

    ``u`` is the cube-root multiscale product in the DYPSA pipeline, but this
    stage treats it as an arbitrary signal. Returns the group-delay function
    and the candidate glottal-closure locations; see `GroupDelayResult`.
    """
    cfg = config if config is not None else GroupDelayConfig()
    u = np.asarray(u, dtype=np.float64)
    if u.ndim != 1:
        raise ValueError(f"u must be 1-D, got shape {u.shape}")

    gw = odd_window_length(cfg.gw_len, fs)
    ham = np.hamming(gw)
    # Antisymmetric linear ramp (gw-1)/2, ..., 1, 0, -1, ..., -(gw-1)/2.
    ramp = ((gw - 1) - 2 * np.arange(gw)) / 2.0
    num_win = ham * ramp  # numerator window: weighted, zero in the middle

    energy = u**2
    numerator = scipy.signal.lfilter(num_win, [1.0], energy)
    denominator = scipy.signal.lfilter(ham, [1.0], energy)
    eps = np.finfo(np.float64).eps
    denominator = denominator.copy()
    denominator[np.abs(denominator) < eps] = 10 * eps  # prevent 0/0

    # Ratio, dropping the (gw-1)-sample filter startup transient.
    centroid = numerator[gw - 1 :] / denominator[gw - 1 :]
    toff = (gw - 1) // 2  # gw is odd, so this is exact

    fw = odd_window_length(cfg.fw_len, fs)
    if fw > 1:
        smooth = np.hamming(fw)
        centroid = scipy.signal.lfilter(smooth, [1.0], centroid) / smooth.sum()
        toff -= (fw - 1) // 2

    # Negative-going zero crossings: index f where y[f] >= 0 and y[f+1] < 0,
    # with linear interpolation for the sub-sample location. NaN fails both
    # comparisons, so it can never register as a crossing.
    nonneg = centroid >= 0
    f = np.nonzero(nonneg[:-1] & ~nonneg[1:])[0]
    slopes = centroid[f + 1] - centroid[f]
    crossings = f - centroid[f] / slopes
    candidates = crossings + toff  # shift into the original-signal frame

    # Aligned, sign-flipped group delay used downstream: prepend toff zeros,
    # drop the last toff samples, negate.
    group_delay = -np.concatenate([np.zeros(toff), centroid[: len(centroid) - toff]])

    return GroupDelayResult(
        group_delay=group_delay,
        centroid=centroid,
        candidates=candidates,
        slopes=slopes,
        toff=toff,
    )
