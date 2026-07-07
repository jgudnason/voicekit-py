"""Configuration for voice-source feature extraction."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FeaturesConfig:
    """Tunable parameters of `extract_voice_features`.

    All knobs are declared here so the config shape is fixed once; fields are
    read as their feature groups land (this component reads only the voicing
    bounds). These are genuine tunable parameters, unlike the structural
    constants elsewhere in the port.
    """

    # Per-cycle framework: a cycle counts as voiced when its period T (samples)
    # falls in (fs/voicing_f0_max, fs/voicing_f0_min) -- i.e. F0 in this range.
    voicing_f0_min: float = 40.0  # Hz
    voicing_f0_max: float = 400.0  # Hz
    # Open/closed timing (used by cq/qoq; the flow-thresholding sub-pipeline).
    open_threshold: float = 0.05  # opThres: open-phase threshold, fraction of peak
    quasi_open_level: float = 0.5  # qoq_level: quasi-open threshold, fraction of peak
    medfilt_window: int = 7  # median-filter length for edge detection
    # Derived glottal flow u = leaky-integrate(udash) at this frequency.
    preemph: float = 10.0  # Hz
    # Spectral features (h1h2/hrf): harmonics considered up to this frequency.
    harmonic_limit_hz: float = 3000.0  # Hz
