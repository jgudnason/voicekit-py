"""Autocorrelation-method LPC via the Levinson-Durbin recursion.

References:
    J. Makhoul (1975), "Linear prediction: A tutorial review",
    Proc. IEEE 63(4), 561-580.

    Reference implementation: VOICEBOX ``v_lpcauto`` (Mike Brookes).
"""

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit.lpc.result import LpcResult


def levinson(
    r: npt.NDArray[np.float64], order: int
) -> tuple[npt.NDArray[np.float64], float, npt.NDArray[np.float64]]:
    """Solve the Toeplitz normal equations by Levinson-Durbin recursion.

    ``r`` holds autocorrelation lags 0..order (at least). Returns
    ``(a, error, reflection)`` where ``a = [1, a1, ..., ap]`` is the
    prediction-error filter, ``error`` the final prediction error energy,
    and ``reflection`` the ``order`` reflection coefficients.
    """
    if order < 1:
        raise ValueError(f"Order must be >= 1, got {order}")
    if len(r) < order + 1:
        raise ValueError(f"Need {order + 1} autocorrelation lags for order {order}, got {len(r)}")

    a = np.zeros(order + 1)
    a[0] = 1.0
    k = np.zeros(order)
    e = float(r[0])
    if e == 0.0:  # all-zero input: unit filter, zero error
        return a, 0.0, k

    for m in range(1, order + 1):
        acc = r[m] + a[1:m] @ r[m - 1 : 0 : -1]
        km = -acc / e
        k[m - 1] = km
        prev = a[1:m].copy()
        a[1:m] = prev + km * prev[::-1]
        a[m] = km
        e *= 1.0 - km * km
        if e <= 0.0:  # perfectly predictable: remaining stages are identity
            e = 0.0
            break
    return a, e, k


def lpc_auto(
    x: npt.NDArray[np.float64],
    order: int,
    window: str | npt.NDArray[np.float64] | None = "hamming",
) -> LpcResult:
    """Autocorrelation-method LPC of one analysis frame.

    The frame is multiplied by ``window`` (a name accepted by
    ``scipy.signal.get_window``, a coefficient array, or None for
    rectangular; default hamming, matching VOICEBOX ``v_lpcauto``), its
    autocorrelation is computed, and the normal equations are solved by
    `levinson`. The resulting filter is guaranteed stable.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError(f"Expected a 1-D frame, got shape {x.shape}")
    if len(x) <= order:
        raise ValueError(f"Frame of {len(x)} samples is too short for order {order}")

    if window is None:
        xw = x
    elif isinstance(window, str):
        xw = x * scipy.signal.get_window(window, len(x), fftbins=False)
    else:
        if len(window) != len(x):
            raise ValueError(f"Window length {len(window)} != frame length {len(x)}")
        xw = x * window

    lags = np.arange(order + 1)
    r = np.array([xw[: len(xw) - lag] @ xw[lag:] for lag in lags])
    a, e, k = levinson(r, order)
    return LpcResult(a=a, error=e, reflection=k)
