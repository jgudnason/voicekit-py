"""Accuracy metrics: hit rate, miss rate, false alarms, timing deviation.

The GCI/GOI scorer follows the YAGA evaluation methodology (Thomas et al. 2012,
reusing DYPSA's strategy, Naylor et al. 2007). See ``score`` for the metric
definitions and REFERENCE_NOTES (SCORE1) for the deliberately-deferred
between-segment false-alarm exclusion and FAT.
"""

from voicekit.eval.score import (
    CycleScore,
    InstantScore,
    Outcome,
    ScoreConfig,
    ScoreResult,
    score_gci_goi,
)

__all__ = [
    "CycleScore",
    "InstantScore",
    "Outcome",
    "ScoreConfig",
    "ScoreResult",
    "score_gci_goi",
]
