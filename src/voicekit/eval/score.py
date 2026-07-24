"""GCI/GOI accuracy scoring, following the YAGA evaluation methodology.

The metric definitions are taken verbatim from the two evaluation papers and are
reproduced in ``REFERENCE_NOTES`` (methodology gate). In brief, following
Thomas, Gudnason & Naylor, *"Estimation of Glottal Closing and Opening Instants
in Voiced Speech Using the YAGA Algorithm,"* IEEE TASLP 20(1), 2012 (§V-A), which
reuses "the strategy defined in [12]" — Naylor, Kounoudes, Gudnason & Brookes,
*"Estimation of Glottal Closure Instants in Voiced Speech Using the DYPSA
Algorithm,"* IEEE TASLP 15(1), 2007 (§IV):

  larynx cycle
      the range of samples ``(n[r-1]+n[r])/2 <= n < (n[r]+n[r+1])/2`` given a
      reference GCI at ``n[r]`` with neighbours ``n[r-1]``, ``n[r+1]``. The cycle
      is only defined for *interior* reference GCIs (both neighbours present); the
      first and last reference GCIs serve as neighbours but bound no scored cycle.
  identification (hit)
      a cycle in which exactly one instant is detected;
  miss
      a cycle in which no instant is detected;
  false alarm
      a cycle in which more than one instant is detected;
  identification error, zeta
      the timing error (estimated - reference) in identification cycles;
  accuracy, sigma / bias, mu
      the standard deviation and mean of zeta (YAGA adds bias mu; DYPSA reports
      sigma alone and folds any constant offset out of accuracy).

**Matching is cycle-based, not window-based.** There is no tunable tolerance that
decides a match; the reference cycle bounds are the disambiguator, derived wholly
from reference GCI positions. The DYPSA "+/-0.25 ms" figure is a *separate*
auxiliary "% of hits within X" statistic, not the match criterion, and is not on
this path.

**Deliberately absent (see REFERENCE_NOTES SCORE1):** the between-voiced-segment
false-alarm exclusion and the FAT metric. The paper underdetermines both what the
"3 ms" measures and how voiced segments are delimited, so they are *structurally
absent* here — no placeholder constant, no segmentation code — not silently
resolved. On a single contiguous voiced segment (all synthetic fixtures, and
OpenGlot) the exclusion is inert and the FA rate below is exactly correct.
Multi-segment references (unvoiced gaps, e.g. APLAWD) must not be scored until
SCORE1 is settled: this scorer builds cycles from *all* consecutive reference
GCIs and so would tile a giant cycle across an unvoiced gap. Callers with such
input must split into voiced segments upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt


class Outcome(StrEnum):
    """The three per-cycle outcomes of GCI/GOI estimation (YAGA Fig. 7)."""

    IDENTIFICATION = "identification"
    MISS = "miss"
    FALSE_ALARM = "false_alarm"


@dataclass(frozen=True)
class ScoreConfig:
    """Explicit, typed scorer configuration (DESIGN: no global mutable config).

    The load-bearing methodology — the larynx-cycle matching rule — has **no**
    free parameter, so this config is intentionally thin. ``std_ddof`` is a
    reporting convention for the accuracy standard deviation, not a fitted value.

    No between-segment / FAT parameters live here: those are structurally absent
    (REFERENCE_NOTES SCORE1), and this config must not grow a placeholder for them.
    """

    std_ddof: int = 0  # population std for sigma; documented convention, not fitted


@dataclass(frozen=True)
class CycleScore:
    """The full scoring decomposition for one reference larynx cycle.

    Every field is here so a fixture can assert *why* a cycle got its outcome, not
    just the aggregate counts: which reference GCI defines the cycle, its bounds,
    which estimated instants fell inside, and the resulting outcome / timing error.
    """

    index: int  # index r into the reference GCI array (interior cycles only)
    ref_gci: float  # the cycle-defining reference GCI, n[r] (samples; may be fractional)
    lo: float  # cycle lower bound (n[r-1]+n[r])/2, inclusive (samples)
    hi: float  # cycle upper bound (n[r]+n[r+1])/2, exclusive (samples)
    ref_instant: float  # reference instant measured against (GCI==ref_gci; GOI==cycle's GOI)
    detections: tuple[int, ...]  # estimated instants in [lo, hi) (samples, sorted; est is integer)
    outcome: Outcome
    timing_error: float | None  # detection - ref_instant (samples); None unless identification


@dataclass(frozen=True)
class InstantScore:
    """Aggregate + decomposed scores for one instant type (GCI or GOI)."""

    n_cycles: int
    n_identification: int
    n_miss: int
    n_false_alarm: int
    id_rate: float  # percent of cycles identified
    miss_rate: float  # percent of cycles missed
    fa_rate: float  # percent of cycles with a false alarm (NO between-segment exclusion; SCORE1)
    accuracy_ms: float | None  # sigma of zeta in ms (None if no timing sample / not applicable)
    bias_ms: float | None  # mu of zeta in ms
    cycles: tuple[CycleScore, ...]  # the per-cycle decomposition, interior cycles in order
    timing_errors_samples: tuple[float, ...]  # zeta per id cycle contributing to sigma/mu

    # Absence markers, so a reader never mistakes "not computed" for a real value or a
    # matching-number coincidence (SCORE1):
    between_segment_exclusion_applied: bool = False  # always False here — structurally absent
    fat: None = None  # False Alarm Total: deferred with the exclusion (SCORE1)


@dataclass(frozen=True)
class ScoreResult:
    """GCI score, and GOI score when GOI inputs were supplied."""

    gci: InstantScore
    goi: InstantScore | None = None

    @property
    def gci_goi_hit_counts_agree(self) -> bool | None:
        """Whether the GCI and GOI identification counts match (``None`` if GOI unscored).

        YAGA notes GCI and GOI hit rates are "necessarily equal" — but that is a
        property of their *reference* construction (one GOI per GCI-defined cycle),
        not of scoring. The scorer counts the two independently, so a mismatch is a
        real data-quality signal (a dropped, extra, or misaligned reference GOI, or
        an LF-derived train of a different count). It is surfaced here for a caller
        to notice, never enforced: a mismatch does not raise and does not warn.
        """
        if self.goi is None:
            return None
        return self.gci.n_identification == self.goi.n_identification


def _validate_reference(name: str, ref: npt.NDArray[np.float64]) -> None:
    if ref.ndim != 1:
        raise ValueError(f"{name} must be 1-D, got shape {ref.shape}")
    if ref.size < 3:
        raise ValueError(
            f"{name} needs >= 3 instants to define one interior larynx cycle, got {ref.size}"
        )
    if np.any(np.diff(ref) <= 0):
        raise ValueError(f"{name} must be strictly increasing (sorted, no duplicates)")


def _cycle_bounds(ref_gci: npt.NDArray[np.float64]) -> list[tuple[int, float, float]]:
    """Interior cycles as ``(r, lo, hi)``: lo/hi are the half-way points to neighbours.

    Only ``r = 1 .. R-2`` yield a cycle; the DYPSA formula needs both neighbours, so
    the first and last reference GCIs bound no scored cycle (they are neighbours only).
    """
    bounds = []
    for r in range(1, ref_gci.size - 1):
        lo = (ref_gci[r - 1] + ref_gci[r]) / 2.0
        hi = (ref_gci[r] + ref_gci[r + 1]) / 2.0
        bounds.append((r, lo, hi))
    return bounds


def _in_window(
    values: npt.NDArray[np.int64] | npt.NDArray[np.float64], lo: float, hi: float
) -> npt.NDArray[np.int64] | npt.NDArray[np.float64]:
    """Instants in ``[lo, hi)`` (lo inclusive, hi exclusive), sorted, dtype preserved.

    Used for both the estimated train (integer, becomes ``detections``) and the
    reference train (float since the retype -- an analytic reference can be
    fractional-sample; REFERENCE_NOTES SCORE2). The boundaries ``lo``/``hi`` are
    themselves the midpoints of consecutive *float* reference instants, so nothing
    on the reference path is ever rounded.
    """
    return np.sort(values[(values >= lo) & (values < hi)])


def _score_instants(
    cycle_ref_gci: npt.NDArray[np.float64],
    ref_instants: npt.NDArray[np.float64],
    est_instants: npt.NDArray[np.int64],
    fs: float,
    accurate: npt.NDArray[np.bool_] | None,
    report_accuracy: bool,
    config: ScoreConfig,
) -> InstantScore:
    """Core scorer over the GCI-defined cycle partition.

    ``cycle_ref_gci`` defines the cycles (always the reference GCIs — this is why
    YAGA states GCI and GOI hit rates are "necessarily equal": one shared
    partition). ``ref_instants`` is the reference train timing is measured against
    (the GCIs themselves for GCI scoring; the GOIs for GOI scoring).

    ``report_accuracy`` decides whether sigma/mu are reported at all; ``accurate``,
    when given, is a per-interior-cycle mask restricting which identification
    cycles contribute (YAGA: GOI accuracy is measured only on reference-accurate
    closed phases). The three live combinations are: GCI —
    ``report_accuracy=True, accurate=None`` (all identification cycles); GOI with a
    reference-accurate flag — ``report_accuracy=True, accurate=mask``; GOI without
    the flag — ``report_accuracy=False`` (sigma/mu omitted, never assumed accurate).
    """
    bounds = _cycle_bounds(cycle_ref_gci)

    cycles: list[CycleScore] = []
    timing_errors: list[float] = []
    n_id = n_miss = n_fa = 0

    for cyc_i, (r, lo, hi) in enumerate(bounds):
        # Reference instant for this cycle: for GCI it is the cycle-defining GCI; for
        # GOI it is the single reference GOI lying inside the cycle. Bin the reference
        # instants the same way we bin detections and require exactly one.
        ref_in = _in_window(ref_instants, lo, hi)
        if ref_in.size != 1:
            raise ValueError(
                f"cycle r={r} [{lo}, {hi}) contains {ref_in.size} reference instants, "
                "expected exactly 1 — reference train is inconsistent with the GCI "
                "cycle partition"
            )
        ref_instant = float(ref_in[0])

        det = tuple(int(x) for x in _in_window(est_instants, lo, hi))
        if len(det) == 1:
            outcome = Outcome.IDENTIFICATION
            zeta = float(det[0] - ref_instant)
            n_id += 1
            # sigma/mu inclusion: all id cycles unless an accurate-mask excludes this one
            if accurate is None or bool(accurate[cyc_i]):
                timing_errors.append(zeta)
            timing_error: float | None = zeta
        elif len(det) == 0:
            outcome = Outcome.MISS
            n_miss += 1
            timing_error = None
        else:
            outcome = Outcome.FALSE_ALARM
            n_fa += 1
            timing_error = None

        cycles.append(
            CycleScore(
                index=r,
                ref_gci=float(cycle_ref_gci[r]),
                lo=lo,
                hi=hi,
                ref_instant=ref_instant,
                detections=det,
                outcome=outcome,
                timing_error=timing_error,
            )
        )

    n_cycles = len(bounds)

    # sigma/mu are omitted entirely when not reported (GOI without a reference-accurate
    # flag), and when there is no contributing timing sample. Never assumed-accurate.
    if not report_accuracy or len(timing_errors) == 0:
        accuracy_ms: float | None = None
        bias_ms: float | None = None
    else:
        z = np.asarray(timing_errors, dtype=np.float64)
        accuracy_ms = float(np.std(z, ddof=config.std_ddof)) / fs * 1000.0
        bias_ms = float(np.mean(z)) / fs * 1000.0

    return InstantScore(
        n_cycles=n_cycles,
        n_identification=n_id,
        n_miss=n_miss,
        n_false_alarm=n_fa,
        id_rate=100.0 * n_id / n_cycles if n_cycles else 0.0,
        miss_rate=100.0 * n_miss / n_cycles if n_cycles else 0.0,
        fa_rate=100.0 * n_fa / n_cycles if n_cycles else 0.0,
        accuracy_ms=accuracy_ms,
        bias_ms=bias_ms,
        cycles=tuple(cycles),
        timing_errors_samples=tuple(timing_errors),
    )


def score_gci_goi(
    est_gci: npt.ArrayLike,
    ref_gci: npt.ArrayLike,
    fs: float,
    *,
    est_goi: npt.ArrayLike | None = None,
    ref_goi: npt.ArrayLike | None = None,
    ref_goi_accurate: npt.ArrayLike | None = None,
    config: ScoreConfig | None = None,
) -> ScoreResult:
    """Score estimated GCIs (and optionally GOIs) against a reference, YAGA-style.

    Parameters
    ----------
    est_gci, ref_gci
        Estimated GCI sample indices (1-D, integer -- the detector emits samples)
        and reference GCI positions (1-D, real-valued). ``ref_gci`` defines the
        larynx-cycle partition and must be strictly increasing. The reference is
        **not rounded** (REFERENCE_NOTES SCORE2): an analytic reference is often
        fractional-sample (OpenGlot R1's ``t_e`` is ``(N1-1)/6``), and rounding it
        would perturb every cycle boundary -- a per-file constant μ bias, or, under
        banker's rounding, a σ corruption. Integer references (e.g. laryngograph
        sample indices) are exact in float64 and handled by the same path.
    fs
        Sampling rate (Hz), used only to convert timing errors to milliseconds.
    est_goi, ref_goi
        Estimated and reference GOI sample indices. GOI is scored only when
        **both** are supplied; otherwise ``ScoreResult.goi`` is ``None``.
    ref_goi_accurate
        Optional per-interior-cycle boolean mask flagging cycles whose reference
        GOI is reliable (YAGA §III: cycles with sliding-CQ std > 0.02 are
        excluded). Its length must equal the number of interior cycles
        (``ref_gci.size - 2``). When absent, GOI **rates** are still reported but
        GOI **accuracy/bias** are omitted (``None``) rather than assumed accurate.

    Notes
    -----
    The between-voiced-segment false-alarm exclusion and the FAT metric are
    structurally absent (REFERENCE_NOTES SCORE1); ``InstantScore.fat`` is always
    ``None`` and ``between_segment_exclusion_applied`` always ``False``. On
    single-segment input the reported ``fa_rate`` is exactly correct.
    """
    config = config or ScoreConfig()
    est_gci_a = np.asarray(est_gci, dtype=np.int64).reshape(-1)
    ref_gci_a = np.asarray(ref_gci, dtype=np.float64).reshape(-1)
    _validate_reference("ref_gci", ref_gci_a)
    if np.any(np.diff(np.sort(est_gci_a)) == 0):
        raise ValueError("est_gci contains duplicate sample indices")

    gci_score = _score_instants(
        cycle_ref_gci=ref_gci_a,
        ref_instants=ref_gci_a,
        est_instants=est_gci_a,
        fs=fs,
        accurate=None,  # GCI: all identification cycles contribute to sigma/mu
        report_accuracy=True,
        config=config,
    )

    goi_score: InstantScore | None = None
    if est_goi is not None and ref_goi is not None:
        est_goi_a = np.asarray(est_goi, dtype=np.int64).reshape(-1)
        ref_goi_a = np.asarray(ref_goi, dtype=np.float64).reshape(-1)

        accurate_a: npt.NDArray[np.bool_] | None = None
        if ref_goi_accurate is not None:
            accurate_a = np.asarray(ref_goi_accurate, dtype=bool).reshape(-1)
            n_interior = ref_gci_a.size - 2
            if accurate_a.size != n_interior:
                raise ValueError(
                    f"ref_goi_accurate has {accurate_a.size} entries, expected one per "
                    f"interior cycle ({n_interior})"
                )

        goi_score = _score_instants(
            cycle_ref_gci=ref_gci_a,
            ref_instants=ref_goi_a,
            est_instants=est_goi_a,
            fs=fs,
            accurate=accurate_a,
            # GOI sigma/mu only when a reference-accurate flag is supplied; absent => omit
            report_accuracy=accurate_a is not None,
            config=config,
        )
    elif est_goi is not None or ref_goi is not None:
        raise ValueError("GOI scoring needs both est_goi and ref_goi, or neither")

    return ScoreResult(gci=gci_score, goi=goi_score)
