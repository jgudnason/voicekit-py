"""Tests for IAIF glottal inverse filtering.

The end-to-end tests synthesize a vowel with a known glottal source
(Rosenberg pulse train) and a known all-pole vocal tract, then check that
IAIF recovers the source: high correlation with the true flow derivative
and strong suppression of the first formant.
"""

import numpy as np
import pytest
import scipy.signal

from voicekit import Signal
from voicekit.iaif import IaifConfig, IaifResult, iaif

F0 = 100.0
FORMANTS = [(500.0, 80.0), (1500.0, 120.0), (2500.0, 200.0)]


def rosenberg_train(fs: int, f0: float, duration: float) -> np.ndarray:
    """Glottal flow as a train of Rosenberg pulses (open 40%, return 16%)."""
    t0 = int(round(fs / f0))
    t1, t2 = int(0.4 * t0), int(0.16 * t0)
    pulse = np.zeros(t0)
    pulse[:t1] = 0.5 * (1 - np.cos(np.pi * np.arange(t1) / t1))
    pulse[t1 : t1 + t2] = np.cos(np.pi * np.arange(t2) / (2 * t2))
    return np.tile(pulse, int(duration * fs / t0))


def synth_vowel(fs: int, duration: float = 0.6) -> tuple[Signal, np.ndarray]:
    """Synthetic vowel plus its true glottal flow derivative."""
    u = rosenberg_train(fs, F0, duration)
    udash = np.diff(u, prepend=0.0)
    poles = []
    for f, bw in FORMANTS:
        if f < 0.45 * fs:
            r = np.exp(-np.pi * bw / fs)
            poles += [r * np.exp(2j * np.pi * f / fs), r * np.exp(-2j * np.pi * f / fs)]
    a_vt = np.poly(poles).real
    speech = scipy.signal.lfilter([1.0], a_vt, udash)
    speech = speech / np.max(np.abs(speech))
    return Signal(samples=np.asarray(speech), fs=fs), udash


def peak_correlation(a: np.ndarray, b: np.ndarray, max_lag: int = 40) -> float:
    """Max normalized cross-correlation of two sequences over small lags."""
    best = 0.0
    for lag in range(-max_lag, max_lag + 1):
        aa = a[max(lag, 0) : len(a) + min(lag, 0)]
        bb = b[max(-lag, 0) : len(b) + min(-lag, 0)]
        c = abs(float(aa @ bb) / np.sqrt(float(aa @ aa) * float(bb @ bb)))
        best = max(best, c)
    return best


@pytest.mark.parametrize("fs", [8000, 20000])
def test_recovers_glottal_flow_derivative(fs: int) -> None:
    signal, udash_true = synth_vowel(fs)
    result = iaif(signal, IaifConfig.for_fs(fs))
    trim = slice(fs // 10, -fs // 10)  # discard edge effects
    corr = peak_correlation(result.glottal_flow_derivative[trim], udash_true[trim])
    # Probe runs achieve 0.99 (8k) / 0.95 (20k); assert with margin
    assert corr > 0.9


def test_suppresses_first_formant() -> None:
    fs = 8000
    signal, _ = synth_vowel(fs)
    result = iaif(signal, IaifConfig.for_fs(fs))
    trim = slice(fs // 10, -fs // 10)

    def f1_to_f0_db(x: np.ndarray) -> float:
        f, p = scipy.signal.welch(x, fs, nperseg=1024)
        return float(10 * np.log10(p[np.argmin(np.abs(f - 500))] / p[np.argmin(np.abs(f - F0))]))

    suppression = f1_to_f0_db(signal.samples[trim]) - f1_to_f0_db(
        result.glottal_flow_derivative[trim]
    )
    assert suppression > 10  # probe runs achieve ~20 dB


def test_output_alignment_and_shapes() -> None:
    signal, _ = synth_vowel(8000)
    result = iaif(signal)
    assert isinstance(result, IaifResult)
    assert len(result.glottal_flow_derivative) == signal.n_samples
    assert len(result.glottal_flow) == signal.n_samples
    assert result.vocal_tract.shape == (len(result.frame_starts), 10 + 1)


def test_flow_is_integrated_derivative() -> None:
    signal, _ = synth_vowel(8000)
    result = iaif(signal)
    redone = scipy.signal.lfilter([1.0], [1.0, -0.95], result.glottal_flow_derivative)
    np.testing.assert_allclose(result.glottal_flow, redone, atol=1e-12)


def test_highpass_can_be_disabled() -> None:
    signal, _ = synth_vowel(8000)
    result = iaif(signal, IaifConfig(highpass=False))
    assert len(result.glottal_flow_derivative) == signal.n_samples


def test_for_fs_scales_vocal_tract_orders() -> None:
    assert IaifConfig.for_fs(8000).vt_order1 == 8
    assert IaifConfig.for_fs(20000).vt_order1 == 20
    assert IaifConfig.for_fs(20000).glottal_order == 4


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="orders"):
        IaifConfig(vt_order1=0)
    with pytest.raises(ValueError, match="Leak"):
        IaifConfig(leak=1.0)
    with pytest.raises(ValueError, match="odd"):
        IaifConfig(hpf_taps=1024)


def test_rejects_too_short_signal() -> None:
    with pytest.raises(ValueError, match="too short"):
        iaif(Signal(samples=np.zeros(5), fs=8000))
