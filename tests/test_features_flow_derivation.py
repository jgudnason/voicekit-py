"""Certification of derive_flow (the "J3" join): udash -> u.

derive_flow integrates the IAIF residual into the glottal flow with the reference's
gain-normalized leaky integrator. J3 is the certification tests/golden/README.md
asks for: derive_flow(captured udash) reproduces the captured feat_u.

feat_u and derive_flow share the same integrator definition, so a common coefficient
slip could cancel and pass the feat_u comparison. To break that, the gain a is also
pinned to an independent literal value, and the SciPy argument order (numerator [a],
denominator [1, -alpha]) is pinned explicitly -- either mistake fails here even if it
would have cancelled against feat_u.
"""

from pathlib import Path

import numpy as np
import pytest
import scipy.signal

from voicekit.features import derive_flow

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]

# a = sqrt(1 / (1 + alpha^2)), alpha = exp(-2*pi*10/fs): the pinned integrator gain.
PINNED_GAIN = {16000: 0.708494, 8000: 0.709878}


@pytest.mark.parametrize("name", FIXTURES)
def test_derive_flow_certifies_against_feat_u(name):
    """J3: derive_flow(captured udash) == feat_u, with the gain and arg order pinned."""
    d = np.load(GOLDEN / f"{name}.npz")
    fs = float(d["input_fs"])
    udash = d["udash"]

    alpha = np.exp(-2 * np.pi * 10.0 / fs)
    a = np.sqrt(1.0 / (1.0 + alpha**2))
    # Independent gain pin: the coefficient itself, not just its effect on feat_u.
    assert a == pytest.approx(PINNED_GAIN[int(fs)], abs=5e-7)

    # Arg-order pin: derive_flow must be lfilter([a], [1, -alpha], .) exactly -- numerator
    # [a] first (MATLAB filter(a, b, .) has a as numerator, b=[1,-alpha] as denominator).
    # A swapped or mis-scaled coefficient fails against this independent build.
    expected = scipy.signal.lfilter([a], [1.0, -alpha], udash)
    np.testing.assert_array_equal(derive_flow(udash, fs), expected)

    # J3 certification: reproduces the captured derived flow at machine epsilon.
    np.testing.assert_allclose(derive_flow(udash, fs), d["feat_u"], rtol=1e-12, atol=1e-14)


def test_derive_flow_cutoff_is_tunable():
    """The cutoff is a plain argument (not a FeaturesConfig knob); it changes u."""
    fs = 16000.0
    udash = np.load(GOLDEN / "vowel_f0100_16k.npz")["udash"]
    u10 = derive_flow(udash, fs, cutoff_hz=10.0)
    u50 = derive_flow(udash, fs, cutoff_hz=50.0)
    assert not np.array_equal(u10, u50)
