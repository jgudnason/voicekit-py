"""Frame-based LPC analysis and time-varying inverse filtering.

Reference implementations: VOICEBOX ``v_lpcauto`` (frame handling) and
``v_lpcifilt`` (piecewise inverse filtering; Mike Brookes).
"""

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit.framing import frame
from voicekit.lpc.autocorrelation import lpc_auto


def lpc_auto_frames(
    x: npt.NDArray[np.float64],
    order: int,
    frame_len: int,
    hop: int,
    window: str | npt.NDArray[np.float64] | None = "hamming",
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64]]:
    """Autocorrelation LPC of successive frames.

    Returns ``(coeffs, starts)``: one row of prediction-error coefficients
    per frame (shape ``(n_frames, order+1)``) and the first sample index of
    each analysis frame. A signal shorter than ``frame_len`` is analyzed as
    a single frame. Trailing samples that do not fill a complete frame are
    not analyzed (they still get filtered — `inverse_filter_frames` extends
    the last frame's coefficients to the end of the signal).
    """
    x = np.asarray(x, dtype=np.float64)
    frames = frame(x, frame_len, hop)
    if len(frames) == 0:
        return lpc_auto(x, order, window).a[None, :], np.zeros(1, dtype=np.int64)
    coeffs = np.stack([lpc_auto(fr, order, window).a for fr in frames])
    starts = np.arange(len(frames), dtype=np.int64) * hop
    return coeffs, starts


def inverse_filter_frames(
    x: npt.NDArray[np.float64],
    coeffs: npt.NDArray[np.float64],
    starts: npt.NDArray[np.int64],
    dc: npt.NDArray[np.float64] | None = None,
) -> npt.NDArray[np.float64]:
    """Inverse filter ``x`` with per-frame coefficients, switching at frame starts.

    Frame ``i``'s prediction-error filter ``A_i(z)`` is applied from
    ``starts[i]`` up to ``starts[i+1]`` (the first frame is extended back to
    the beginning of the signal, the last to its end). Each segment's filter
    is warmed up on the ``order`` preceding samples; because ``A(z)`` is FIR,
    this makes the piecewise result identical to global filtering wherever
    the coefficients agree. Matches VOICEBOX ``v_lpcifilt`` with ``fade=0``.

    ``dc`` is an optional per-frame DC level subtracted from the signal before
    filtering (``filter(A_i, 1, x - dc[i])``), reproducing ``v_lpcifilt``'s ``dc``
    input -- the closed-phase covariance solve fits a DC jointly and subtracts it
    here. **Omitting ``dc`` (the default) is byte-identical to the plain form**, so
    every existing caller is unaffected.
    """
    if len(coeffs) != len(starts):
        raise ValueError(f"Got {len(coeffs)} coefficient rows but {len(starts)} frame starts")
    if np.any(np.diff(starts) <= 0):
        raise ValueError("Frame starts must be strictly increasing")
    if dc is not None and len(dc) != len(coeffs):
        raise ValueError(f"Got {len(dc)} dc values but {len(coeffs)} coefficient rows")
    order = coeffs.shape[1] - 1
    n = len(x)
    y = np.empty(n)
    for i, a in enumerate(coeffs):
        lo = 0 if i == 0 else int(starts[i])
        hi = int(starts[i + 1]) if i < len(coeffs) - 1 else n
        if lo >= n:
            break
        ctx = max(0, lo - order)
        seg = x[ctx:hi] if dc is None else x[ctx:hi] - dc[i]
        y[lo:hi] = scipy.signal.lfilter(a, [1.0], seg)[lo - ctx :]
    return y
