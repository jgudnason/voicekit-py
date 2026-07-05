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
    """

    a: npt.NDArray[np.float64]
    error: float
    reflection: npt.NDArray[np.float64] | None = None

    @property
    def order(self) -> int:
        return len(self.a) - 1
