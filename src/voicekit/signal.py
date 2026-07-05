"""Core signal container used throughout voicekit."""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class Signal:
    """A mono audio signal: samples plus sampling frequency.

    ``samples`` is always a read-only 1-D float64 array; input is coerced
    on construction. ``source`` optionally records where the signal came
    from (e.g. a filename) for diagnostics.
    """

    samples: npt.NDArray[np.float64]
    fs: int
    source: str | None = field(default=None, compare=False)

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.float64)
        if samples.ndim != 1:
            raise ValueError(f"Signal requires a 1-D (mono) array, got shape {samples.shape}")
        if self.fs <= 0:
            raise ValueError(f"Sampling frequency must be positive, got {self.fs}")
        samples = samples.copy()
        samples.flags.writeable = False
        object.__setattr__(self, "samples", samples)

    @property
    def n_samples(self) -> int:
        return len(self.samples)

    @property
    def duration(self) -> float:
        """Signal duration in seconds."""
        return self.n_samples / self.fs

    def times(self) -> npt.NDArray[np.float64]:
        """Sample times in seconds (same length as ``samples``)."""
        return np.arange(self.n_samples) / self.fs
