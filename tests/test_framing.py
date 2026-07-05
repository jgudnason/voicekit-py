"""Tests for framing utilities."""

import numpy as np
import pytest

from voicekit import frame, frame_times


def test_shapes_and_contents() -> None:
    x = np.arange(10, dtype=np.float64)
    frames = frame(x, frame_len=4, hop=2)
    assert frames.shape == (4, 4)
    np.testing.assert_array_equal(frames[0], [0, 1, 2, 3])
    np.testing.assert_array_equal(frames[1], [2, 3, 4, 5])
    np.testing.assert_array_equal(frames[3], [6, 7, 8, 9])


def test_trailing_samples_dropped() -> None:
    x = np.arange(11, dtype=np.float64)
    frames = frame(x, frame_len=4, hop=2)
    assert frames.shape == (4, 4)  # sample 10 does not fill a frame


def test_no_overlap() -> None:
    x = np.arange(9, dtype=np.float64)
    frames = frame(x, frame_len=3, hop=3)
    assert frames.shape == (3, 3)
    np.testing.assert_array_equal(frames[2], [6, 7, 8])


def test_short_input_gives_zero_frames() -> None:
    frames = frame(np.zeros(3), frame_len=4, hop=2)
    assert frames.shape == (0, 4)


def test_is_view_not_copy() -> None:
    x = np.arange(10, dtype=np.float64)
    frames = frame(x, frame_len=4, hop=2)
    assert frames.base is not None  # shares memory with x


def test_rejects_bad_params() -> None:
    with pytest.raises(ValueError, match="positive"):
        frame(np.zeros(10), frame_len=0, hop=2)
    with pytest.raises(ValueError, match="positive"):
        frame(np.zeros(10), frame_len=4, hop=0)


def test_frame_times_match_frames() -> None:
    x = np.zeros(10)
    frames = frame(x, frame_len=4, hop=2)
    times = frame_times(len(x), frame_len=4, hop=2, fs=100)
    assert len(times) == len(frames)
    assert times[0] == pytest.approx(1.5 / 100)  # center of samples 0..3
    assert times[1] == pytest.approx(3.5 / 100)


def test_frame_times_short_input() -> None:
    assert len(frame_times(3, frame_len=4, hop=2, fs=100)) == 0
