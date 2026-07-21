"""Result container for LPC analysis."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class LpcResult:
    """Coefficients and residual energy from one LPC analysis.

    ``a`` is the prediction-error filter ``[1, a1, ..., ap]``: applying
    ``A(z)`` to the analyzed samples yields the residual, i.e.
    ``x[n] ≈ -(a[1]*x[n-1] + ... + a[p]*x[n-p])``. This matches the
    convention of VOICEBOX ``v_lpcauto``/``v_lpccovar`` and MATLAB ``lpc``.

    ``error`` is the energy (sum of squares, weighted where applicable) of
    the prediction residual over the analyzed samples.

    ``reflection`` holds the reflection coefficients when the solver
    produces them (autocorrelation method only).

    ``signal_energy`` is the (unweighted) energy of the analyzed *target*
    samples -- the same samples the residual ``error`` is evaluated over. It
    mirrors the signal-energy column of VOICEBOX ``v_lpccovar``'s ``e`` output
    (``e(:,2)``), so a caller can read both the signal and residual energy from
    one analysis. Only the covariance solver sets it; the autocorrelation solver
    leaves it ``None``.

    ``dc`` is the jointly-fitted DC level from the ``dc_offset`` covariance fit
    (VOICEBOX ``v_lpccovar``'s third output, ``dc = aa(1)/sum(ar)``): the constant
    ``DC`` such that the residual is ``A(z)*(s - DC)``. It is what the closed-phase
    inverse filter subtracts per frame (``v_lpcifilt``'s ``dc``). ``None`` unless
    ``dc_offset`` was set.
    """

    a: npt.NDArray[np.float64]
    error: float
    reflection: npt.NDArray[np.float64] | None = None
    signal_energy: float | None = None
    dc: float | None = None

    @property
    def order(self) -> int:
        return len(self.a) - 1
