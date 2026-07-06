"""MATLAB-compatibility numerical helpers shared across YAGA stages.

Kept in one place so the rounding convention is single-sourced: every site
that rounds a value to a sample index in the DYPSA pipeline must match
MATLAB's ``round`` (half away from zero), not numpy's (half to even).
"""

import numpy as np
import numpy.typing as npt


def matlab_round(x: npt.NDArray[np.float64] | float) -> npt.NDArray[np.float64]:
    """Round half away from zero, as MATLAB ``round`` does.

    numpy's ``round`` is half-to-even, which diverges on the ``k.5`` cases
    that arise throughout DYPSA (midpoint gaps, window half-lengths, candidate
    positions) and would shift the resulting sample index.
    """
    return np.sign(x) * np.floor(np.abs(x) + 0.5)
