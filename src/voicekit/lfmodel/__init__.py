"""Liljencrants-Fant (LF) glottal model.

Forward *timing* landmarks (`lf_timing`) are provided now; LF-model *fitting*
(recovering shape parameters from an observed flow) is deferred (step 9 scope).
"""

from voicekit.lfmodel.timing import LfTiming, lf_timing

__all__ = ["LfTiming", "lf_timing"]
