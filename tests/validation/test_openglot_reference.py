"""R1 reference construction: the non-circular checks on the closed form.

The load-bearing caution (REFERENCE_NOTES OG-GCI-A, and the reviewer's warning at
the gate): the closed form is *both* the reference constructor and, for the GCI
train itself, its own known answer -- so a test asserting the train against the
same formula is circular and proves nothing. The non-circular content lives in
two places, and only these are asserted as evidence for the closed form:

- **Test B** -- the period equals the length the 48 kHz pulse actually resamples
  to. This ties the closed-form period to an independent operation (resampling a
  synthesised pulse), not to itself.
- **A'-2** -- the reconstructed ``-dU/dt`` pulse attains its global minimum at the
  grid index ``N1-1`` the closed form places ``t_e`` at, with value ``-Ee``. This
  is a property of the LF parameter sets, established by synthesis, that could
  have been false.

The ``reference_gci_train`` tests below assert *structure* (spacing, phase,
bounds, float-ness), never that the train equals the formula -- that would be the
circular check.
"""

import numpy as np
import pytest
from scipy.signal import resample_poly
from validation.openglot.reference import (
    FSH,
    MODE_PARAMS,
    R1_FS,
    pulse_period,
    reconstruct_lf_pulse,
    reference_gci_train,
)

MODES = sorted(MODE_PARAMS)
F0S = list(range(100, 361, 20))  # RepositoryI: 100-360 Hz in 20-Hz steps (14 values)
ALL_COMBINATIONS = [(m, float(f0)) for m in MODES for f0 in F0S]


class TestBPeriod:
    """Test B: closed-form period == resampled 48 kHz pulse length, zero tolerance."""

    @pytest.mark.parametrize(("mode", "f0"), ALL_COMBINATIONS)
    def test_period_equals_resampled_pulse_length(self, mode: str, f0: float) -> None:
        pulse = reconstruct_lf_pulse(mode, f0)
        resampled_len = len(resample_poly(pulse.deriv48, int(R1_FS), int(FSH)))
        assert pulse_period(mode, f0) == resampled_len


class TestAPrime2:
    """A'-2: t_e is the global -dU/dt minimum of the LF pulse, at index N1-1."""

    @pytest.mark.parametrize(("mode", "f0"), ALL_COMBINATIONS)
    def test_te_is_global_derivative_minimum_at_n1_minus_1(self, mode: str, f0: float) -> None:
        pulse = reconstruct_lf_pulse(mode, f0)
        # (i) the global minimum of the full pulse is exactly the open-phase endpoint
        assert int(np.argmin(pulse.deriv48)) == pulse.n1 - 1
        # (ii) the value there is -Ee (the excitation amplitude)
        assert pulse.deriv48[pulse.n1 - 1] == pytest.approx(-pulse.ee_gain, rel=1e-9)
        # (iii) nothing dips below -Ee before t_e (open phase never overshoots)
        assert pulse.deriv48[: pulse.n1].min() >= -pulse.ee_gain * (1.0 + 1e-9)


class TestReferenceTrainStructure:
    """Structure of the scored train -- never equality with the formula (circular)."""

    def test_spacing_is_the_pulse_period(self) -> None:
        train = reference_gci_train("normal", 140.0, n_samples=1600)
        period = pulse_period("normal", 140.0)
        diffs = np.diff(train)
        assert np.all(diffs == period)  # uniform, integer period

    def test_phase_is_fractional_and_first_instant_is_the_closure_of_pulse_zero(self) -> None:
        # normal 140 Hz: N1=196 -> phase (N1-1)/6 = 32.5, deliberately un-rounded.
        train = reference_gci_train("normal", 140.0, n_samples=1600)
        assert train[0] == pytest.approx(32.5, abs=1e-12)
        assert train.dtype == np.float64
        assert float(train[0]) != round(float(train[0]))  # genuinely fractional

    def test_all_instants_within_bounds(self) -> None:
        n = 1600
        for mode, f0 in ALL_COMBINATIONS:
            train = reference_gci_train(mode, f0, n_samples=n)
            assert train.size > 0
            assert train[0] >= 0.0
            assert train[-1] < n

    def test_empty_when_signal_shorter_than_first_instant(self) -> None:
        # phase ~32.5 samples; a 10-sample signal contains no instant.
        train = reference_gci_train("normal", 140.0, n_samples=10)
        assert train.size == 0

    def test_unknown_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown phonation mode"):
            reference_gci_train("bogus", 140.0, n_samples=1600)
        with pytest.raises(ValueError, match="unknown phonation mode"):
            pulse_period("bogus", 140.0)


class TestPhaseInvariant:
    """The constructor asserts its own fractional structure (SCORE2 layering)."""

    def test_holds_for_all_parameter_sets(self) -> None:
        # If the invariant were wrong for any real set, reference_gci_train would raise.
        for mode, f0 in ALL_COMBINATIONS:
            reference_gci_train(mode, f0, n_samples=1600)  # no raise

    def test_non_integer_rate_ratio_raises(self) -> None:
        # fs that does not divide 48000 -> the resample is not an integer ratio.
        with pytest.raises(ValueError, match="integer ratio"):
            reference_gci_train("normal", 140.0, n_samples=1600, fs=7000.0)

    def test_denominator_six_structure_is_what_is_asserted(self) -> None:
        # A legitimate integer-ratio fs (16 kHz -> ratio 3) still satisfies the
        # grid-index invariant, proving the check is structural, not fs==8000.
        reference_gci_train("normal", 140.0, n_samples=1600, fs=16000.0)  # no raise


def test_covers_all_56_parameter_sets() -> None:
    # Guard the claim "over all 56 combinations": if RepositoryI's grid changes,
    # this fails rather than silently testing a subset.
    assert len(ALL_COMBINATIONS) == 56
