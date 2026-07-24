"""OpenGlot reference construction (see REFERENCE_NOTES OG-GCI, OG-GCI-A..D).

OpenGlot ships no GCI/GOI annotations, so every reference we score against is
constructed here -- deliberately in ``validation/``, not ``src/voicekit``, so the
scorer (`voicekit.eval.score_gci_goi`) stays definition-agnostic: it takes bare
instant arrays and never learns where they came from. This package owns the
OpenGlot-specific definitional choices (the phonation-mode parameter table, the
48 kHz pulse-length arithmetic, the ``t_e`` placement), each ratified in the
ledger before code.
"""
