"""The voiced/unvoiced analysis frame grid (`VoicingGrid`).

A fixed-frame time-partition for the voicing detector: 32 ms frames every 10 ms
(the reference ``vuvMeasurements`` defaults; the Atal-Rabiner paper itself uses
10 ms non-overlapping blocks -- see REFERENCE_NOTES VUV6/VUV10 for the corrected
attribution). Durations are held in milliseconds
and turned into sample counts at the signal's own sampling rate -- no internal
resampling -- which makes the grid **input-neutral**: the frame-centre samples are
identical whatever signal is framed (raw, residual, or flow), so locking the grid
commits none of the open input leans. (A later classifier-design choice to
resample to a fixed internal rate would re-open that neutrality; see
REFERENCE_NOTES "Step 7 (VUV)" VUV6.)

`VoicingGrid` is deliberately its **own** config, not derived from `IaifConfig`.
The two share a 32 ms frame length by coincidence only: they differ on hop
(10 vs 16 ms) and serve different purposes (voicing discrimination vs glottal
inverse filtering), so a later IAIF framing change must not move the voicing
grid. ``test_vuv_grid`` enforces that the durations are `VoicingGrid`'s own
literals, not shared-by-reference with `IaifConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True)
class VoicingGrid:
    """Fixed-frame grid for the voicing track and the derived per-cycle mask.

    ``frame_dur_s``/``hop_dur_s`` are in seconds; sample counts are derived at a
    given ``fs`` (``round(dur * fs)``), so one grid definition serves every rate.
    """

    frame_dur_s: float = 0.032  # frame length (s) -- reference vuvMeasurements wl
    hop_dur_s: float = 0.010  # hop / frame step (s) -- reference vuvMeasurements inc

    def frame_len(self, fs: float) -> int:
        """Frame length in samples at ``fs``."""
        return round(self.frame_dur_s * fs)

    def hop(self, fs: float) -> int:
        """Frame step in samples at ``fs``."""
        return round(self.hop_dur_s * fs)

    def guard_band_samples(self, fs: float) -> float:
        """W = frame_len/2 + hop/2: window-straddle plus nearest-centre alignment
        slack. The scoring guard band and the D1 mask-exercise margin both use it."""
        return self.frame_len(fs) / 2 + self.hop(fs) / 2

    def frame_centers(self, n_samples: int, fs: float) -> npt.NDArray[np.float64]:
        """0-based centre sample of each full frame in an ``n_samples`` signal.

        Centre of frame ``k`` is ``k*hop + (frame_len-1)/2`` (half-integer when the
        frame length is even). Trailing samples that do not fill a frame are dropped.
        """
        fl, hp = self.frame_len(fs), self.hop(fs)
        n_frames = max(0, (n_samples - fl) // hp + 1)
        return np.asarray(np.arange(n_frames) * hp + (fl - 1) / 2, dtype=np.float64)

    def project(self, sample: int, fs: float) -> int:
        """Nearest-centre frame index for a sample: ``round((s-(frame_len-1)/2)/hop)``.

        Pure grid arithmetic, independent of signal length -- may return an index
        outside ``[0, n_frames)`` for samples near the signal edges; the caller
        clamps against the actual track length. This is the single source for the
        derived mask's GCI -> frame lookup.
        """
        return project_to_frame(sample, self.frame_len(fs), self.hop(fs))


def project_to_frame(sample: int, frame_len: int, hop: int) -> int:
    """Nearest-centre frame index for ``sample``: ``round((s-(frame_len-1)/2)/hop)``.

    **The single copy of the projection formula.** `VoicingGrid.project` (from a
    grid + fs) and `VoicingTrack.frame_index` (from a self-describing track's own
    ``frame_len``/``hop``) both delegate here, so the derived per-cycle mask's
    GCI -> frame lookup uses this arithmetic and no re-derived second copy.
    """
    return round((sample - (frame_len - 1) / 2) / hop)
