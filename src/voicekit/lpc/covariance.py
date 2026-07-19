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
    dc_offset: bool = False,
) -> LpcResult:
    """Covariance-method LPC, minimizing weighted squared prediction error.

    The prediction error is evaluated at samples ``n = order .. len(x)-1``
    (each predicted from the ``order`` preceding samples, so no windowing
    and no edge effects). ``weights`` is a full-length nonnegative array
    aligned with ``x``; entries before ``x[order]`` are unused. Weighting
    the error by ``weights[n]`` lets callers emphasize regions such as the
    glottal closed phase. Default is uniform (plain covariance method).

    WEIGHT CONVENTION (load-bearing for step 8): this minimises
    ``sum weights[n] * resid[n]^2`` — the error is weighted by ``weights``
    *linearly*. The reference VOICEBOX ``v_lpccovar`` instead weights the error
    by ``W^2`` (it applies its weight as ``dm.*w`` / ``sc = s.*w``; its header
    says "the error at each sample is weighted by W^2"). So a caller reproducing
    a ``v_lpccovar`` run with reference weight vector ``W`` — every step-8
    weighted-LP GIF method (closed-phase, AME, Gaussian) does exactly this —
    must pass ``weights = W**2``, not ``W``. This was pinned by golden master
    against ``v_lpccovar`` (``tests/test_lpc.py::TestWeightedCovarianceConvention``,
    machine-eps on both the plain and ``dc_offset`` paths), not by matching
    Python output. See REFERENCE_NOTES "GIF weighting convention (W vs W^2)".

    ``dc_offset`` reproduces VOICEBOX ``v_lpccovar``'s three-output form
    (``[ar,e,dc]``): a constant regressor is added to the design so the AR
    coefficients are fitted about a jointly-fitted DC level rather than about
    zero (``s(n)-DC`` instead of ``s(n)``). ``a`` and ``error`` are then the AR
    coefficients and residual energy of that DC-included fit; ``signal_energy``
    is unchanged (the window energy is DC-independent). The fitted DC itself is
    not returned — no caller needs it (the reference's ``vuvMeasurements``
    requests it only to trigger the modification, then discards it). Default
    off: the design is not augmented and the result is bit-identical to the
    plain covariance method.

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

    # DC-offset (v_lpccovar 3-output): append a constant regressor so a DC level
    # is fitted jointly with the AR lags. Appended vs the reference's prepended
    # column is least-squares-invariant to column order, so the AR coefficients
    # agree (pinned by test); appending gives clean coef[:order] slicing.
    design = np.column_stack([past, np.ones(len(target))]) if dc_offset else past

    # Solve the weighted least-squares problem via sqrt-weighted lstsq
    # rather than forming normal equations (better conditioning). sqrt(w) here
    # means the error is weighted by w LINEARLY (min sum w*resid^2). v_lpccovar
    # weights by W^2; reproducing it requires the caller pass weights = W^2. See
    # the docstring's WEIGHT CONVENTION note and REFERENCE_NOTES (W vs W^2).
    sw = np.sqrt(w)
    coef_full, *_ = np.linalg.lstsq(sw[:, None] * design, -sw * target, rcond=None)
    coef = coef_full[:order]  # AR lags; drops the DC coefficient when dc_offset

    a = np.concatenate(([1.0], coef))
    residual = target + design @ coef_full
    error = float(w @ (residual * residual))
    # Signal energy over the same target samples the residual is measured on --
    # unweighted (v_lpccovar's e(:,2)), so a caller reads both energies from one
    # call (e.g. the VUV Es/Ep features single-source their energies here).
    signal_energy = float(target @ target)
    return LpcResult(a=a, error=error, signal_energy=signal_energy)
