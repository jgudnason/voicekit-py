"""Path-dependent DP cost kernels for YAGA GCI selection.

Two of the dynamic program's cost terms cannot be precomputed as per-candidate
vectors (unlike those in ``dp_costs``): each depends on the path the DP is
building. They are provided here as pure functions the recursion (piece 5)
evaluates per transition:

    * waveform similarity -- a normalized cross-correlation between the residual
      windows around a candidate and the previous selected GCI;
    * pitch deviation -- a cost on the current period differing from the previous
      one, so it needs the previous two GCIs.

Both are returned *unweighted* (the DP applies ``dy_wxcorr``/``dy_wpitch``), so
they match the unweighted captured cost columns directly.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), DYPSA, IEEE
    TASLP 15(1), 34-43.

    Reference implementation: the ``q_cas`` and ``f_cp`` computations in the DP
    loop of the VOICEBOX-bundled ``dypsagoi.m``. Reimplemented from the algorithm
    description, not ported. Two reproduced reference quirks are flagged inline
    and recorded in REFERENCE_NOTES.md.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

# Structural constants (hardcoded in the reference, not tunable parameters).
_WAVEFORM_BIAS = -0.5  # makes similar windows a negative (favourable) cost
_PITCH_OFFSET = 0.5  # baseline of the pitch-deviation cost


@dataclass(frozen=True)
class WaveformSimilarityConfig:
    """Parameter of the waveform-similarity kernel (voicebox ``dy_xwlen``)."""

    xwlen: float = 0.01  # cross-correlation window duration (s)


@dataclass(frozen=True)
class PitchDeviationConfig:
    """Parameter of the pitch-deviation kernel (voicebox ``dy_spitch``)."""

    spitch: float = 0.2  # period-deviation scale


def waveform_similarity(
    residual: npt.NDArray[np.float64],
    r_positions: npt.NDArray[np.int64],
    q_positions: npt.NDArray[np.int64],
    fs: float,
    config: WaveformSimilarityConfig | None = None,
) -> npt.NDArray[np.float64]:
    """Unweighted waveform-similarity cost between candidate and previous-GCI windows.

    ``residual`` is the IAIF residual (``udash``) -- **not** the speech
    ``s_used``; the reference DP correlates residual windows. For each aligned
    pair ``(r, q)`` (1-based sample positions) the cost is
    ``-0.5 * (nx2-1)/(nx2-2) * corr(window_r, window_q)`` where ``corr`` is the
    Pearson correlation of the two windows; similar windows give a negative
    (favourable) cost.
    """
    cfg = config if config is not None else WaveformSimilarityConfig()
    residual = np.asarray(residual, dtype=np.float64)
    r = np.atleast_1d(np.asarray(r_positions)).astype(np.int64)
    q = np.atleast_1d(np.asarray(q_positions)).astype(np.int64)

    nxc = int(np.ceil(cfg.xwlen * fs))
    half = nxc // 2
    # Asymmetric window: one extra sample on the right (-half .. half+1). The
    # reference keeps this +1 for DYPSA-2 compatibility and flags it as a
    # probable bug. See REFERENCE_NOTES.md entry 1.
    wavix = np.arange(-half, half + 2)
    nx2 = wavix.size

    # 1-based positions -> 0-based indices at window extraction.
    win_r = residual[(r[:, None] - 1) + wavix[None, :]]
    win_q = residual[(q[:, None] - 1) + wavix[None, :]]

    sum_r, sum_q = win_r.sum(axis=1), win_q.sum(axis=1)
    cov = (win_r * win_q).sum(axis=1) - sum_r * sum_q / nx2
    var_r = (win_r * win_r).sum(axis=1) - sum_r**2 / nx2
    var_q = (win_q * win_q).sum(axis=1) - sum_q**2 / nx2
    pearson = cov / np.sqrt(var_r * var_q)

    # The (nx2-1)/(nx2-2) factor compensates a bug in a superseded helper and is
    # kept for parity; a prior reference revision ran without it. See
    # REFERENCE_NOTES.md entry 2.
    return np.asarray(_WAVEFORM_BIAS * (nx2 - 1) / (nx2 - 2) * pearson, dtype=np.float64)


def pitch_deviation(
    current_period: npt.NDArray[np.float64],
    previous_period: npt.NDArray[np.float64],
    config: PitchDeviationConfig | None = None,
) -> npt.NDArray[np.float64]:
    """Unweighted pitch-deviation cost from the current and previous periods.

    With ``a`` the current period (``r - q``) and ``b`` the previous (``q - p``),
    the normalized deviation ``f_nx = 2 - 2(a+b)/((a+b)+|a-b|)`` is 0 for equal
    periods and grows as they diverge; the cost is ``0.5 - exp(sv2i*f_nx**2)``,
    so equal periods give exactly -0.5. This is the normal-transition cost only;
    the talkspurt-start override (previous period 0 -> ``dy_cspurt``) belongs to
    the DP's spurt logic, not this kernel.
    """
    cfg = config if config is not None else PitchDeviationConfig()
    a = np.asarray(current_period, dtype=np.float64)
    b = np.asarray(previous_period, dtype=np.float64)

    total = a + b
    f_nx = 2.0 - 2.0 * total / (total + np.abs(a - b))  # 2s are structural
    sv2i = -1.0 / (2.0 * cfg.spitch**2)  # = -12.5 at the default spitch=0.2
    return np.asarray(_PITCH_OFFSET - np.exp(sv2i * f_nx**2), dtype=np.float64)
