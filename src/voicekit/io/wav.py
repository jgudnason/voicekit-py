"""Wav file reading and writing.

Uses scipy.io.wavfile; per DESIGN.md, ``soundfile`` may replace this the
first time a real corpus file breaks it. Samples are normalized to
float64 in [-1, 1), following the convention of VOICEBOX ``readwav``.
"""

from pathlib import Path

import numpy as np
from scipy.io import wavfile

from voicekit.signal import Signal


def read_wav(path: str | Path) -> Signal:
    """Read a mono wav file into a `Signal`, scaled to [-1, 1).

    Integer PCM is scaled by its full-scale value (e.g. int16 by 2**15);
    float wav data is passed through unscaled.
    """
    path = Path(path)
    fs, data = wavfile.read(path)
    if data.ndim != 1:
        raise ValueError(
            f"{path} has {data.shape[1]} channels; only mono files are supported for now"
        )
    if data.dtype == np.uint8:  # 8-bit wav is unsigned, offset binary
        samples = (data.astype(np.float64) - 128.0) / 128.0
    elif np.issubdtype(data.dtype, np.integer):
        samples = data.astype(np.float64) / float(-np.iinfo(data.dtype).min)
    else:
        samples = data.astype(np.float64)
    return Signal(samples=samples, fs=int(fs), source=str(path))


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
