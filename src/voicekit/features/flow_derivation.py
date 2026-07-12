"""Derive the glottal flow ``u`` from the IAIF flow derivative ``udash``.

The reference feature pipeline (``vsaTools/testSingleFile.m``) does not feed the
IAIF residual straight into ``extractVoiceFeatures``; it first integrates it into
the flow with a gain-normalized leaky integrator::

    b = [1, -exp(-2*pi*f_preemph/fs)]
    a = sqrt(1 / sum(b.^2))
    u = filter(a, b, uu)          % MATLAB: a is the numerator, b the denominator

i.e. a one-pole leaky integrator (pole at ``alpha = exp(-2*pi*cutoff/fs)``) scaled
so its coefficient energy is unity. This is *de-emphasis / integration* -- it turns
the derivative back into flow -- despite the reference naming the cutoff
``f_preemph``; genuine pre-emphasis is the FIR high-pass in `YagaConfig.preemph`,
the opposite operation. Kept out of `extract_voice_features` because the reference
passes the already-derived ``u`` in (and the golden ``feat_u`` capture is fed to the
feature groups directly).

Reference: ``vsaTools/testSingleFile.m``; reimplemented, not ported.
"""

import numpy as np
import numpy.typing as npt
import scipy.signal

_DEFAULT_CUTOFF_HZ = 10.0  # the reference's f_preemph


def derive_flow(
    residual: npt.NDArray[np.float64], fs: float, cutoff_hz: float = _DEFAULT_CUTOFF_HZ
) -> npt.NDArray[np.float64]:
    """Integrate the IAIF residual ``udash`` into the glottal flow ``u``.

    ``residual`` is the IAIF flow derivative (``YagaResult.residual``); ``fs`` the
    sampling rate; ``cutoff_hz`` the leaky-integrator cutoff (the reference's
    ``f_preemph``, default 10 Hz). Returns ``u = filter(a, [1, -alpha], residual)``
    with ``alpha = exp(-2*pi*cutoff_hz/fs)`` and gain ``a = sqrt(1/(1+alpha**2))``.

    The MATLAB call is ``filter(a, b, uu)`` -- ``a`` (a scalar) is the numerator and
    ``b = [1, -alpha]`` the denominator; SciPy takes the numerator first, so this is
    ``scipy.signal.lfilter([a], [1, -alpha], residual)``.
    """
    residual = np.asarray(residual, dtype=np.float64)
    alpha = np.exp(-2 * np.pi * cutoff_hz / fs)
    gain = np.sqrt(1.0 / (1.0 + alpha**2))  # a = sqrt(1/sum(b^2)), b = [1, -alpha]
    return np.asarray(scipy.signal.lfilter([gain], [1.0, -alpha], residual))
