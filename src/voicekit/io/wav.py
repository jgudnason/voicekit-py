"""Wav file reading and writing.

Uses scipy.io.wavfile; per DESIGN.md, ``soundfile`` may replace this the
first time a real corpus file breaks it. Samples are normalized to
float64 in [-1, 1), following the convention of VOICEBOX ``readwav``.
"""

from pathlib import Path

import numpy as np
from scipy.io import wavfile

from voicekit.signal import Signal


def read_wav(path: str | Path, *, channel: int | None = None) -> Signal:
    """Read a wav file into a mono `Signal`, scaled to [-1, 1).

    Integer PCM is scaled by its full-scale value (e.g. int16 by 2**15);
    float wav data is passed through unscaled.

    ``channel`` selects one channel of a multi-channel file (0-based). It is
    **required** for multi-channel input -- there is no default channel, because
    which channel is read is a load-bearing choice, not a formatting detail: on a
    corpus shipping speech pressure alongside glottal flow, reading the wrong one
    yields a plausible wrong answer rather than an error. Passing ``channel`` for
    a mono file is allowed only as ``0``, so a caller may always be explicit.

    When ``channel`` is given, ``Signal.source`` records it as ``"<path>#ch<n>"``
    so the choice travels with the signal instead of living only at the call site.
    """
    path = Path(path)
    fs, data = wavfile.read(path)
    if data.ndim == 1:
        if channel is not None and channel != 0:
            raise ValueError(f"{path} is mono; channel must be 0 or None, got {channel}")
    else:
        n_channels = data.shape[1]
        if channel is None:
            raise ValueError(
                f"{path} has {n_channels} channels; pass channel=<0..{n_channels - 1}> "
                "to select one (there is no default channel)"
            )
        if not 0 <= channel < n_channels:
            raise ValueError(
                f"{path} has {n_channels} channels; channel must be in "
                f"[0, {n_channels - 1}], got {channel}"
            )
        data = data[:, channel]
    source = str(path) if channel is None else f"{path}#ch{channel}"
    if data.dtype == np.uint8:  # 8-bit wav is unsigned, offset binary
        samples = (data.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(data.dtype, np.integer):
        samples = data.astype(np.float64) / float(-np.iinfo(data.dtype).min)
    else:
        samples = data.astype(np.float64)
    return Signal(samples=samples, fs=int(fs), source=source)


def write_wav(signal: Signal, path: str | Path) -> None:
    """Write a `Signal` to a 16-bit PCM wav file.

    Samples are expected in [-1, 1); values outside that range raise
    rather than clipping silently.
    """
    peak = float(np.max(np.abs(signal.samples), initial=0.0))
    if peak > 1.0:
        raise ValueError(f"Samples exceed [-1, 1] (peak {peak:.4g}); rescale before writing")
    pcm = np.round(signal.samples * 32767.0).astype(np.int16)
    wavfile.write(Path(path), signal.fs, pcm)
