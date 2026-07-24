"""OpenGlot R1 stratification, pinned before any R1 number exists (SCORE2 gate).

The ratified split (a stratification decision made after a σ is visible would be a
rule-1 violation, so it is fixed here):

- **primary**, pooled: ``normal``, ``breathy``, ``creaky``.
- **whispery**, a separate stratum, reported apart, never pooled with the primary
  trio -- weak excitation (``Ee = 10^(-4.6/20)``, the weakest by far). Its GCI
  reference is the same analytic ``t_e``, so its *standing* is PRIMARY even though
  its *stratum* is separate: stratum separation and reference authority are
  orthogonal axes.
- **vowel** and **f0** are *breakdowns*, not strata: same standing, shown for
  distribution. f0 is reported at all 14 values -- no binning, no threshold (a cut
  chosen later would be rule-1).
"""

from __future__ import annotations

from validation.report import Standing, Stratum

PRIMARY = Stratum(
    name="primary", members=("normal", "breathy", "creaky"), standing=Standing.PRIMARY
)
# Separate stratum, PRIMARY standing (analytic t_e reference); never pooled with PRIMARY.
WHISPERY = Stratum(name="whispery", members=("whispery",), standing=Standing.PRIMARY)

STRATA = (PRIMARY, WHISPERY)

# Disaggregation axes -- same standing, distribution only. f0: all 14 values, no cut.
BREAKDOWN_AXES = ("vowel", "f0")

_MODE_TO_STRATUM = {m: s for s in STRATA for m in s.members}


def stratum_of(mode: str) -> Stratum:
    """The stratum a phonation mode belongs to; raise for an unknown mode."""
    try:
        return _MODE_TO_STRATUM[mode]
    except KeyError:
        known = sorted(_MODE_TO_STRATUM)
        raise ValueError(f"unknown phonation mode {mode!r}; known: {known}") from None


def pooled_stratum(modes: tuple[str, ...]) -> Stratum:
    """The single stratum ``modes`` all belong to; raise if they span more than one.

    This is the construction-time guard: pooling a primary mode with whispery (or
    any cross-stratum set) raises rather than producing a σ over mixed standing.
    """
    strata = {stratum_of(m).name for m in modes}
    if len(strata) != 1:
        raise ValueError(f"cannot pool across strata: modes {modes} span strata {sorted(strata)}")
    return stratum_of(modes[0])
