"""Framing utilities: slice a signal into (overlapping) analysis frames."""

import numpy as np
import numpy.typing as npt


def frame(x: npt.NDArray[np.float64], frame_len: int, hop: int) -> npt.NDArray[np.float64]:
    """Slice ``x`` into frames of ``frame_len`` samples every ``hop`` samples.

    Returns a read-only 2-D view of shape ``(n_frames, frame_len)`` — no
    copy is made, so this is cheap even for long signals. Trailing samples
    that do not fill a complete frame are dropped.
    """
    if frame_len <= 0 or hop <= 0:
        raise ValueError(f"frame_len and hop must be positive, got {frame_len=}, {hop=}")
    if len(x) < frame_len:
        return np.empty((0, frame_len), dtype=x.dtype)
    windows = np.lib.stride_tricks.sliding_window_view(x, frame_len)
    return windows[::hop]


def frame_times(n_samples: int, frame_len: int, hop: int, fs: int) -> npt.NDArray[np.float64]:
    """Center time (seconds) of each frame produced by `frame`."""
    n_frames = max(0, (n_samples - frame_len) // hop + 1)
    starts = np.arange(n_frames) * hop
    return (starts + (frame_len - 1) / 2) / fs
