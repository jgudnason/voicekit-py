"""Tests for the VUV conditioning helper and its precondition check.

The filter's expected values come from the paper's Eq. (1) evaluated
analytically here, independently of the module's coefficient construction --
a known-value test, not a self-comparison. The check's tests use **inline**
DC/hum constructions; the committed DC/hum fixture lands separately, per
VUV12's derive -> predict -> check.
"""

import warnings

import numpy as np
import pytest
from scipy.signal import freqz

from voicekit.signal import Signal
from voicekit.vuv.conditioning import (
    SUB_SPEECH_BAND_HZ,
    ConditioningConfig,
    check_precondition,
    condition,
    eq1_coefficients,
)


def _analytic_eq1(f_hz, fs):
    """H(e^{jw}) straight from the paper's Eq. (1) -- an independent oracle."""
    a, b, t = 130.0 * 2 * np.pi, 200.0 * 2 * np.pi, 1.0 / fs
    z = np.exp(2j * np.pi * f_hz / fs)
    num = 1.0 - 2.0 * z**-1 + z**-2
    den = 1.0 - 2.0 * np.exp(-a * t) * np.cos(b * t) * z**-1 + np.exp(-2.0 * a * t) * z**-2
    return num / den


def test_coefficients_match_the_papers_literal_values_at_10k():
    # The generalization is T -> 1/fs (VUV10), so at the paper's own 10 kHz the
    # coefficients must reproduce its literal T = 1e-4 constants. This is the
    # source check: it fails if T is generalized any other way.
    num, den = eq1_coefficients(10000.0)
    a, b, t = 130.0 * 2 * np.pi, 200.0 * 2 * np.pi, 1e-4
    assert np.allclose(num, [1.0, -2.0, 1.0], rtol=0, atol=0)
    assert np.allclose(
        den,
        [1.0, -2.0 * np.exp(-a * t) * np.cos(b * t), np.exp(-2.0 * a * t)],
        rtol=1e-15,
    )


def test_response_matches_analytic_eq1_across_frequencies():
    fs = 16000.0
    freqs = np.array([50.0, 60.0, 90.0, 120.0, 180.0, 200.0, 500.0, 1000.0, 4000.0])
    num, den = eq1_coefficients(fs)
    _, h = freqz(num, den, worN=2 * np.pi * freqs / fs)
    assert np.allclose(h, _analytic_eq1(freqs, fs), rtol=1e-12)


def test_double_zero_at_dc_is_exact():
    # H(1) = 0 exactly: the numerator [1, -2, 1] sums to zero in IEEE. This is
    # the property that makes the filter high-pass -- the paper prints the
    # numerator as z^2, and this is what pins it to z^-2.
    num, _ = eq1_coefficients(16000.0)
    assert num.sum() == 0.0


def test_poles_match_the_analytic_radius_and_angle():
    fs = 16000.0
    _, den = eq1_coefficients(fs)
    poles = np.sort_complex(np.roots(den))
    r = np.exp(-130.0 * 2 * np.pi / fs)  # radius exp(-a/fs)
    theta = 200.0 * 2 * np.pi / fs  # angle b/fs
    expected = np.sort_complex(np.array([r * np.exp(1j * theta), r * np.exp(-1j * theta)]))
    assert np.allclose(poles, expected, rtol=1e-12)


def test_analog_prototype_is_fs_invariant():
    # STRUCTURAL: T -> 1/fs means one fixed analog prototype (a 200 Hz/260 Hz
    # resonator) realized at each rate, so the response at a given Hz is the
    # same at any rate. This is the test that fails if the generalization is
    # ever "simplified" to something else.
    #
    # Tolerance, named: T -> 1/fs places the poles by MATCHED-Z, so the digital
    # realization only APPROXIMATES the analog prototype -- measured deviation
    # across 8k/16k/44.1k vs 10k is 2.2e-5, which is discretization, not error.
    # rtol=1e-3 sits ~45x above that and ~600x below what it must catch: the
    # wrong generalization (T pinned at the paper's 1e-4, ignoring fs) deviates
    # by 6.4e-1. Not a fitted tolerance -- a well-separated one.
    freqs = np.array([50.0, 120.0, 200.0, 1000.0])
    resp = []
    for fs in (10000.0, 16000.0, 44100.0):
        num, den = eq1_coefficients(fs)
        _, h = freqz(num, den, worN=2 * np.pi * freqs / fs)
        ref = freqz(num, den, worN=[2 * np.pi * 1000.0 / fs])[1][0]
        resp.append(np.abs(h / ref))
    assert np.allclose(resp[0], resp[1], rtol=1e-3)
    assert np.allclose(resp[0], resp[2], rtol=1e-3)


def test_condition_removes_dc_and_leaves_a_new_signal():
    fs = 16000
    rng = np.random.default_rng(0)
    x = rng.standard_normal(4000) + 5.0  # gross DC offset
    sig = Signal(samples=x, fs=fs, source="inline")
    out = condition(sig)
    assert out is not sig
    assert out.samples is not sig.samples
    assert np.array_equal(sig.samples, x)  # helper did not touch the input
    assert out.fs == fs
    # DC is gone after the filter settles (the double zero at z=1 kills it).
    assert abs(out.samples[1000:].mean()) < 0.05 * abs(x.mean())


def test_condition_attenuates_hum_far_more_than_a_fundamental():
    # The ratified claim (VUV12): it attenuates a low fundamental rather than
    # annihilating it, while hitting hum hard. Asserted as the decomposition,
    # against the analytic response rather than a measured output.
    fs = 16000.0
    hum = abs(_analytic_eq1(np.array([50.0]), fs))[0]
    f0_low = abs(_analytic_eq1(np.array([90.0]), fs))[0]
    passband = abs(_analytic_eq1(np.array([1000.0]), fs))[0]
    assert 20 * np.log10(hum / passband) < -25.0  # hum crushed
    assert -20.0 < 20 * np.log10(f0_low / passband) < -10.0  # F0 bent, not broken


def test_check_raises_on_dc():
    rng = np.random.default_rng(1)
    x = rng.standard_normal(8000) + 2.0
    with pytest.raises(ValueError, match="DC offset"):
        check_precondition(Signal(samples=x, fs=16000, source="inline"))


def test_check_warns_on_hum_and_does_not_raise():
    # Enforcement tracks confidence: hum WARNS (the named cost of the shakier
    # sub-band threshold), it does not raise.
    fs = 16000
    n = 16000
    t = np.arange(n) / fs
    rng = np.random.default_rng(2)
    x = 0.05 * rng.standard_normal(n) + np.sin(2 * np.pi * 50.0 * t)  # hum-dominated
    with pytest.warns(UserWarning, match="below 70 Hz"):
        report = check_precondition(Signal(samples=x, fs=fs, source="inline"))
    assert report.sub_band_violation
    assert not report.dc_violation


def test_check_is_silent_on_clean_signal():
    # A zero-mean, speech-band signal: the fixtures' regime. No DC, no rumble.
    fs = 16000
    t = np.arange(16000) / fs
    rng = np.random.default_rng(3)
    x = np.sin(2 * np.pi * 200.0 * t) + 0.1 * rng.standard_normal(16000)
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the test
        report = check_precondition(Signal(samples=x, fs=fs, source="inline"))
    assert not report.dc_violation
    assert not report.sub_band_violation


def test_check_is_read_only():
    rng = np.random.default_rng(4)
    x = rng.standard_normal(8000) + 3.0
    original = x.copy()
    sig = Signal(samples=x, fs=16000, source="inline")
    check_precondition(sig, enforce=False)
    assert np.array_equal(x, original)  # never rewrites its input


def test_enforce_false_reports_without_raising():
    # The explicit opt-out: measured and reported, no raise -- "ignored"
    # becomes "decided", on the record in the caller's code.
    rng = np.random.default_rng(5)
    x = rng.standard_normal(8000) + 2.0
    report = check_precondition(Signal(samples=x, fs=16000, source="inline"), enforce=False)
    assert report.dc_violation
    assert report.mean_rms_ratio > 0.1


def test_committed_fixtures_already_satisfy_the_precondition():
    # rho_env caveat (a): the fixtures are zero-mean synthetic with no
    # sub-speech-band content, so they comply UNCONDITIONED -- which is why
    # VUV11/VUV13's measurements are of precondition-compliant signals and owe
    # no conditioning. Guards that claim against fixture drift.
    from tests.synthetic.vuv_fixture import load_discriminating_fixture

    for name in ("vuv_d1_offset_16k", "vuv_d2_vfric_16k", "vuv_d3_breathy_16k"):
        fx = load_discriminating_fixture(name)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            report = check_precondition(fx.signal)
        assert not report.dc_violation, name
        assert not report.sub_band_violation, name


def test_config_is_the_papers_values():
    cfg = ConditioningConfig()
    assert cfg.a_hz == 130.0  # a = 130*2*pi rad/s
    assert cfg.b_hz == 200.0  # b = 200*2*pi rad/s
    assert SUB_SPEECH_BAND_HZ == 70.0  # check band != filter corner
