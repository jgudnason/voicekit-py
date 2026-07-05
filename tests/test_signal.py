"""Tests for the core Signal container."""

import numpy as np
import pytest

from voicekit import Signal


def test_basic_properties() -> None:
    sig = Signal(samples=np.zeros(8000), fs=16000)
    assert sig.n_samples == 8000
    assert sig.duration == pytest.approx(0.5)
    assert sig.times()[0] == 0.0
    assert sig.times()[-1] == pytest.approx((8000 - 1) / 16000)


def test_coerces_to_float64() -> None:
    sig = Signal(samples=np.array([1, 2, 3], dtype=np.int16), fs=8000)
    assert sig.samples.dtype == np.float64


def test_samples_are_immutable() -> None:
    sig = Signal(samples=np.zeros(10), fs=8000)
    with pytest.raises(ValueError):
        sig.samples[0] = 1.0


def test_constructor_copies_input() -> None:
    x = np.zeros(10)
    sig = Signal(samples=x, fs=8000)
    x[0] = 42.0
    assert sig.samples[0] == 0.0


def test_rejects_stereo() -> None:
    with pytest.raises(ValueError, match="1-D"):
        Signal(samples=np.zeros((10, 2)), fs=8000)


def test_rejects_bad_fs() -> None:
    with pytest.raises(ValueError, match="positive"):
        Signal(samples=np.zeros(10), fs=0)
