"""Sampling-rate conversion."""

import math

import scipy.signal

from voicekit.signal import Signal


def resample(signal: Signal, fs_new: int) -> Signal:
    """Resample to ``fs_new`` Hz using polyphase filtering.

    Rational-factor conversion via ``scipy.signal.resample_poly``, which
    applies an anti-aliasing filter appropriate to the rate change.
    """
    if fs_new <= 0:
        raise ValueError(f"Target sampling frequency must be positive, got {fs_new}")
    if fs_new == signal.fs:
        return signal
    g = math.gcd(fs_new, signal.fs)
    resampled = scipy.signal.resample_poly(signal.samples, up=fs_new // g, down=signal.fs // g)
    return Signal(samples=resampled, fs=fs_new, source=signal.source)
