"""voicekit: voice analysis from first principles.

Glottal inverse filtering, glottal closure/opening instant (GCI/GOI)
detection, and voice source feature extraction. See DESIGN.md in the
repository for scope and architecture.
"""

from voicekit.framing import frame, frame_times
from voicekit.signal import Signal

__version__ = "0.1.0.dev0"

__all__ = ["Signal", "frame", "frame_times", "__version__"]
