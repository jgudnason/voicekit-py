"""Stationary (undecimated) wavelet transform and multiscale product.

The first stage of YAGA GCI detection. The glottal-flow-derivative residual
is decomposed with an à-trous stationary wavelet transform (bior1.5,
3 levels); the product of the detail coefficients across scales sharpens
the excitation peaks at glottal closure while suppressing noise that does
not persist across scales (Bouzid & Ellouze; Sturmel et al.).

à-trous SWT: at each level the signal is filtered by the wavelet's
decomposition filters *without* decimation, and the filters are upsampled
(zeros inserted between taps) for the next level rather than the signal
downsampled. Every level therefore returns full-length coefficient rows.
The boundary is handled by circular (periodic) convolution.

One deliberate departure from the textbook SWT: the output is aligned so
that level-k coefficient ``n`` is the circular convolution centred with an
offset of ``lf//2 - 1`` samples (``lf`` the upsampled filter length), one
sample earlier than stock MATLAB ``swt``. This matches the ``swtalign``
routine used by the reference DYPSA detector, against whose captured output
this module is validated; downstream group-delay and dynamic-programming
stages are tuned to that alignment.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), "Estimation
    of Glottal Closure Instants in Voiced Speech using the DYPSA Algorithm",
    IEEE TASLP 15(1), 34-43.

    Reference implementation for the alignment convention: the ``swtalign``
    subfunction of the reference GCI/GOI detector. Reimplemented here
    from the à-trous algorithm description, not ported.
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

# bior1.5 decomposition filters, in MATLAB ``wfilters('bior1.5','d')``
# convention (the reference's). The lowpass is the length-10 spline filter;
# the highpass is the short Haar-like detail filter, zero-padded to length 10.
# These are the runtime source of truth; ``tests/test_yaga_swt.py`` checks
# them against the committed capture and against PyWavelets so the values
# here cannot drift silently.
BIOR15_LO_D: npt.NDArray[np.float64] = np.array(
    [
        0.016572815184060,
        -0.016572815184060,
        -0.121533978016438,
        0.121533978016438,
        0.707106781186548,
        0.707106781186548,
        0.121533978016438,
        -0.121533978016438,
        -0.016572815184060,
        0.016572815184060,
    ]
)
BIOR15_HI_D: npt.NDArray[np.float64] = np.array(
    [0.0, 0.0, 0.0, 0.0, -0.707106781186548, 0.707106781186548, 0.0, 0.0, 0.0, 0.0]
)


@dataclass(frozen=True)
class SwtResult:
    """Stationary wavelet coefficients, one row per level, aligned to the input.

    ``approx[k]`` and ``detail[k]`` are the level-``k+1`` approximation and
    detail coefficients (``k`` from 0), each the same length as the input
    signal.
    """

    approx: npt.NDArray[np.float64]
    detail: npt.NDArray[np.float64]


def _atrous_filter(
    x: npt.NDArray[np.float64], taps: npt.NDArray[np.float64], level: int
) -> npt.NDArray[np.float64]:
    """Apply one à-trous filter level as circular convolution with the SWT offset.

    The level-``level`` filter places the base ``taps`` at stride
    ``2**(level-1)`` (zeros between), giving length ``lf = len(taps) * stride``.
    Output sample ``n`` is ``sum_k f_up[k] * x[(n + lf//2 - 1 - k) mod s]``.
    """
    n = x.shape[0]
    stride = 1 << (level - 1)
    lf = taps.shape[0] * stride
    shift = lf // 2 - 1
    out = np.zeros(n)
    for i, coeff in enumerate(taps):
        # f_up has tap i at position i*stride; contributes x[(n - (i*stride - shift)) mod s].
        out += coeff * np.roll(x, i * stride - shift)
    return out


def stationary_wavelet_transform(
    x: npt.NDArray[np.float64],
    levels: int = 3,
    lo_d: npt.NDArray[np.float64] = BIOR15_LO_D,
    hi_d: npt.NDArray[np.float64] = BIOR15_HI_D,
) -> SwtResult:
    """à-trous stationary wavelet transform, aligned to the reference convention.

    The signal is zero-padded at the tail to a multiple of ``2**levels`` (the
    à-trous cascade needs a length divisible by the coarsest stride), the
    transform is run at full resolution on every level, and the coefficient
    rows are trimmed back to the original length. Callers pass any-length
    signals and get rows aligned sample-for-sample with the input.
    """
    if levels < 1:
        raise ValueError(f"levels must be >= 1, got {levels}")
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 1:
        raise ValueError(f"x must be 1-D, got shape {x.shape}")
    n = x.shape[0]

    pow2 = 1 << levels
    n_pad = pow2 * -(-n // pow2)  # round up to a multiple of 2**levels
    padded = np.zeros(n_pad)
    padded[:n] = x

    approx = np.empty((levels, n_pad))
    detail = np.empty((levels, n_pad))
    current = padded
    for level in range(1, levels + 1):
        # Both rows are computed from the same (pre-update) approximation.
        detail[level - 1] = _atrous_filter(current, hi_d, level)
        current = _atrous_filter(current, lo_d, level)
        approx[level - 1] = current

    return SwtResult(approx=approx[:, :n], detail=detail[:, :n])


def multiscale_product(
    x: npt.NDArray[np.float64],
    levels: int = 3,
    lo_d: npt.NDArray[np.float64] = BIOR15_LO_D,
    hi_d: npt.NDArray[np.float64] = BIOR15_HI_D,
) -> npt.NDArray[np.float64]:
    """Product of the detail coefficients across all levels (the multiscale product).

    Its negative peaks localize glottal closure; the sign handling and cube
    root that follow in the GCI branch live with the candidate-generation
    stage, not here.
    """
    detail = stationary_wavelet_transform(x, levels, lo_d, hi_d).detail
    return np.prod(detail, axis=0)


def negative_cube_root(mp: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Cube root of the negatively half-wave-rectified multiscale product (GCI branch).

    The GCI detector uses the *negative* half of the multiscale product (the
    positive half is zeroed), then takes the cube root to compress the dynamic
    range while preserving sign. This is deliberately kept out of
    `multiscale_product`, which stays sign-neutral and reusable: the GOI branch
    needs the mirror-image positive-half sibling of this transform.
    """
    mp = np.asarray(mp, dtype=np.float64)
    return np.cbrt(np.where(mp > 0, 0.0, mp))
