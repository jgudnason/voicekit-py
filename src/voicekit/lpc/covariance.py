"""Covariance-method LPC with optional per-sample error weighting.

The weighted variant is the foundation of the glottal inverse filtering
methods in ``voicekit.gif``: closed-phase, AME, and Gaussian-weighted LP
are all just choices of the ``weights`` array (see DESIGN.md §9 step 8).

References:
    J. Makhoul (1975), "Linear prediction: A tutorial review",
    Proc. IEEE 63(4), 561-580.

    C. Magi, J. Pohjalainen, T. Backstrom, P. Alku (2009), "Stabilised
    weighted linear prediction", Speech Communication 51(5), 401-411.

    Reference implementation: VOICEBOX ``v_lpccovar`` (Mike Brookes),
    which weights the error at each sample and notes the closed-phase
    application directly.
"""

import numpy as np
import numpy.typing as npt

from voicekit.lpc.result import LpcResult


def lpc_covar(
    x: npt.NDArray[np.float64],
    order: int,
    weights: npt.NDArray[np.float64] | None = None,
) -> LpcResult:
    """Covariance-method LPC, minimizing weighted squared prediction error.

    The prediction error is evaluated at samples ``n = order .. len(x)-1``
    (each predicted from the ``order`` preceding samples, so no windowing
    and no edge effects). ``weights`` is a full-length nonnegative array
    aligned with ``x``; entries before ``x[order]`` are unused. Weighting
    the error by ``weights[n]`` lets callers emphasize regions such as the
    glottal closed phase. Default is uniform (plain covariance method).

    Unlike `lpc_auto`, the resulting filter is not guaranteed stable —
    the classic trade-off of the covariance method.
    """
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError(f"Expected a 1-D frame, got shape {x.shape}")
    if len(x) < 2 * order + 1:
        raise ValueError(
            f"Frame of {len(x)} samples is too short for order {order}; need >= {2 * order + 1}"
        )
    if weights is None:
        w = np.ones(len(x) - order)
    else:
        weights = np.asarray(weights, dtype=np.float64)
        if len(weights) != len(x):
            raise ValueError(f"Weights length {len(weights)} != signal length {len(x)}")
        if np.any(weights < 0):
            raise ValueError("Weights must be nonnegative")
        w = weights[order:]

    # Rows: x[n-1], ..., x[n-order] for each predicted sample n
    past = np.column_stack([x[order - k : len(x) - k] for k in range(1, order + 1)])
    target = x[order:]

    # Solve the weighted least-squares problem via sqrt-weighted lstsq
    # rather than forming normal equations (better conditioning).
    sw = np.sqrt(w)
    coef, *_ = np.linalg.lstsq(sw[:, None] * past, -sw * target, rcond=None)

    a = np.concatenate(([1.0], coef))
    residual = target + past @ coef
    error = float(w @ (residual * residual))
    # Signal energy over the same target samples the residual is measured on --
    # unweighted (v_lpccovar's e(:,2)), so a caller reads both energies from one
    # call (e.g. the VUV Es/Ep features single-source their energies here).
    signal_energy = float(target @ target)
    return LpcResult(a=a, error=error, signal_energy=signal_energy)
