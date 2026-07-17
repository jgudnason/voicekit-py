"""Voiced/unvoiced/silence detection.

Input precondition (canonical statement -- other modules point here rather
than restating it)
------------------------------------------------------------------------
**Input to this package must be DC-free and free of sub-speech-band energy**
(below 70 Hz: mains hum, rumble, DC offset -- energy phonation does not
explain). ``voicekit.vuv.conditioning.SUB_SPEECH_BAND_HZ`` is the band edge;
70 Hz is the modal phonation floor, and is deliberately *not* the conditioning
filter's 200 Hz corner, which sits above many speakers' F0.

*Why it is a contract and not a convenience.* Low-frequency energy drives the
voicing statistic ``r1`` toward 1, so an unconditioned recording reads as
confidently voiced -- wrong, confident, and quiet. Mains hum is the hard case:
it is **genuinely periodic**, so no threshold on any correlation statistic can
reject it, at any significance level, ever, and once it is in the frame it is
undetectable downstream by construction. The defense exists only at the input
boundary (REFERENCE_NOTES VUV12).

*How to meet it.* Any adequate high-pass will do; a recording that never had
DC or rumble (synthetic fixtures, for instance) already complies.
`voicekit.vuv.condition` is an explicit helper that applies the source paper's
own front-end filter (Atal & Rabiner 1976, Eq. (1); 200 Hz) -- sufficient, not
necessary, and never applied for you: the detector analyzes exactly the signal
it is handed.

*How it is enforced.* `voicekit.vuv.check_precondition` reads the input and
never rewrites it, raising on DC and warning on sub-band energy -- enforcement
tracking each check's confidence. Both are escapable only explicitly, so
"ignored" becomes "decided".
"""

from voicekit.vuv.conditioning import (
    ConditioningConfig,
    PreconditionReport,
    check_precondition,
    condition,
)
from voicekit.vuv.decision import r1
from voicekit.vuv.features import (
    FrameFeatures,
    VuvFeaturesConfig,
    extract_frame_features,
)
from voicekit.vuv.grid import VoicingGrid

__all__ = [
    "ConditioningConfig",
    "FrameFeatures",
    "PreconditionReport",
    "VoicingGrid",
    "VuvFeaturesConfig",
    "check_precondition",
    "condition",
    "extract_frame_features",
    "r1",
]
