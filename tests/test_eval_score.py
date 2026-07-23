"""Synthetic validation of the GCI/GOI scorer (step 9, sequence step 2).

Every fixture here is hand-countable: reference GCIs on a round grid, estimated
instants placed one at a time into named cycles. The assertions check the
**decomposition** — which estimated instant landed in which reference cycle, by
the half-way-point rule, and why each cycle earned its outcome — not merely the
aggregate rates. A test that checked only the final rates could not catch a
binning error that happens to preserve the counts.

Grid used throughout: ``fs = 10000`` Hz, reference GCIs every 100 samples at
100..600. Six reference GCIs give **four interior larynx cycles** (the first and
last GCI bound no scored cycle — the DYPSA formula needs both neighbours):

    r=1  ref 200  ->  [150, 250)
    r=2  ref 300  ->  [250, 350)
    r=3  ref 400  ->  [350, 450)
    r=4  ref 500  ->  [450, 550)

At fs=10000, 1 sample = 0.1 ms, so timing arithmetic is trivial to verify by hand.
"""

from __future__ import annotations

from typing import get_type_hints

import numpy as np
import pytest

from voicekit.eval import Outcome, ScoreResult, score_gci_goi
from voicekit.eval.score import InstantScore, ScoreConfig

FS = 10000.0
REF_GCI = np.array([100, 200, 300, 400, 500, 600], dtype=np.int64)
# The four interior cycles, as (r, lo, hi):
BOUNDS = [(1, 150.0, 250.0), (2, 250.0, 350.0), (3, 350.0, 450.0), (4, 450.0, 550.0)]


def _by_index(result_cycles):
    return {c.index: c for c in result_cycles}


def test_one_of_each_outcome_full_decomposition():
    """One identification / miss / false-alarm / identification across the four cycles.

    est_gci = [203, 400, 410, 498]:
      * 203 -> cycle r=1 [150,250): single detection -> IDENTIFICATION, zeta=+3
      * (nothing in [250,350))          cycle r=2   -> MISS
      * 400, 410 -> cycle r=3 [350,450): two detections -> FALSE_ALARM
      * 498 -> cycle r=4 [450,550): single detection -> IDENTIFICATION, zeta=-2
    """
    est = np.array([203, 400, 410, 498], dtype=np.int64)
    res = score_gci_goi(est, REF_GCI, FS)
    gci = res.gci

    # --- decomposition: bounds + which detections landed where + why each outcome ---
    cyc = _by_index(gci.cycles)
    assert [c.index for c in gci.cycles] == [1, 2, 3, 4]
    for (r, lo, hi) in BOUNDS:
        assert (cyc[r].lo, cyc[r].hi) == (lo, hi)

    assert cyc[1].detections == (203,)
    assert cyc[1].outcome is Outcome.IDENTIFICATION
    assert cyc[1].ref_instant == 200
    assert cyc[1].timing_error == pytest.approx(3.0)  # est - ref = 203 - 200

    assert cyc[2].detections == ()  # nothing in [250, 350)
    assert cyc[2].outcome is Outcome.MISS
    assert cyc[2].timing_error is None

    assert cyc[3].detections == (400, 410)  # two in one cycle
    assert cyc[3].outcome is Outcome.FALSE_ALARM
    assert cyc[3].timing_error is None

    assert cyc[4].detections == (498,)
    assert cyc[4].outcome is Outcome.IDENTIFICATION
    assert cyc[4].timing_error == pytest.approx(-2.0)  # 498 - 500

    # --- aggregates follow from the decomposition ---
    assert (gci.n_cycles, gci.n_identification, gci.n_miss, gci.n_false_alarm) == (4, 2, 1, 1)
    assert gci.id_rate == pytest.approx(50.0)
    assert gci.miss_rate == pytest.approx(25.0)
    assert gci.fa_rate == pytest.approx(25.0)

    # zeta = [+3, -2] samples; mean 0.5, population std 2.5 samples; 1 sample = 0.1 ms
    assert gci.timing_errors_samples == (3.0, -2.0)
    assert gci.bias_ms == pytest.approx(0.05)  # 0.5 sample * 0.1 ms
    assert gci.accuracy_ms == pytest.approx(0.25)  # 2.5 samples * 0.1 ms


def test_deferred_markers_present():
    """The deferred pieces (SCORE1) carry their current marker values.

    These are value assertions, not structural pins — the structural pins live in
    ``test_fat_is_typed_none_never_numeric`` and the two field-set tests. Here we
    only check that ``fat`` reads ``None`` and the exclusion flag reads ``False``,
    so no second false-alarm number is emitted that could be misread as independent
    corroboration of ``fa_rate``.
    """
    res = score_gci_goi(np.array([203], dtype=np.int64), REF_GCI, FS)
    assert res.gci.fat is None
    assert res.gci.between_segment_exclusion_applied is False


def test_fat_is_typed_none_never_numeric():
    """FAT's absence is a structural fact of the type, not just its current value.

    ``fat`` is annotated ``None`` (not ``float | None``), so a caller can never read
    it as ``0`` or a computed rate. This test breaks the moment someone retypes it to
    compute a value.
    """
    assert get_type_hints(InstantScore)["fat"] is type(None)
    res = score_gci_goi(np.array([203, 400, 410], dtype=np.int64), REF_GCI, FS)
    assert res.gci.fat is None
    assert not isinstance(res.gci.fat, (int, float))  # None is neither


def test_scoreconfig_surface_is_pinned_against_a_between_segment_parameter():
    """The config carries no between-segment / 3 ms / exclusion parameter.

    Pinning the field set means any future SCORE1 implementation that adds such a
    parameter must break this test — a conscious acknowledgement, not a silent
    re-introduction of a tunable matching window.
    """
    assert set(ScoreConfig.__dataclass_fields__) == {"std_ddof"}


def test_instantscore_surface_is_pinned_against_a_parallel_fat_field():
    """InstantScore carries no computed false-alarm field beside the None-typed fat.

    Same mechanism as the config-surface pin, closing the 'add a parallel
    fat_computed field' route: introducing any new field (a real FAT, or a
    between-segment count) must break this test.
    """
    assert set(InstantScore.__dataclass_fields__) == {
        "n_cycles",
        "n_identification",
        "n_miss",
        "n_false_alarm",
        "id_rate",
        "miss_rate",
        "fa_rate",
        "accuracy_ms",
        "bias_ms",
        "cycles",
        "timing_errors_samples",
        "between_segment_exclusion_applied",
        "fat",
    }


def test_between_segment_flag_stays_false_when_false_alarms_present():
    """Single-segment behavioral test: a false-alarm cycle is counted, not excluded.

    This is NOT a structural pin. A real between-segment code path only affects
    multi-segment input and would leave this single-segment case unchanged (flag
    still False, FA still counted). It documents the single-segment behaviour: every
    false alarm contributes to ``fa_rate`` and no exclusion is applied.
    """
    # cycle r=3 has two detections -> a false alarm that is *counted*, not excluded
    res = score_gci_goi(np.array([400, 410], dtype=np.int64), REF_GCI, FS)
    assert res.gci.n_false_alarm == 1
    assert res.gci.fa_rate == pytest.approx(25.0)  # counted, nothing excluded
    assert res.gci.between_segment_exclusion_applied is False


def test_gci_goi_hit_counts_agree_is_observable_but_not_enforced():
    """A caller can notice GCI/GOI hit-count divergence without diffing cycles.

    None when GOI unscored; True when counts match; False on a divergence, which is
    reported (not raised) as a data-quality signal.
    """
    gci_only = score_gci_goi(np.array([203], dtype=np.int64), REF_GCI, FS)
    assert gci_only.gci_goi_hit_counts_agree is None

    # matching: both identify r1 and r4
    match = score_gci_goi(
        np.array([203, 498], dtype=np.int64),
        REF_GCI,
        FS,
        est_goi=np.array([233, 528], dtype=np.int64),
        ref_goi=REF_GOI,
    )
    assert match.gci_goi_hit_counts_agree is True

    # divergence: GCI identifies r1 and r4 (2), GOI identifies only r1 (1) — no raise
    diverge = score_gci_goi(
        np.array([203, 498], dtype=np.int64),
        REF_GCI,
        FS,
        est_goi=np.array([233], dtype=np.int64),
        ref_goi=REF_GOI,
    )
    assert diverge.gci.n_identification == 2
    assert diverge.goi is not None and diverge.goi.n_identification == 1
    assert diverge.gci_goi_hit_counts_agree is False


def test_cycle_boundary_is_lo_inclusive_hi_exclusive():
    """A detection exactly on a shared boundary belongs to the upper cycle.

    250 is hi of r=1 and lo of r=2. It must fall in r=2 (hi-exclusive), leaving r=1
    a miss.
    """
    res = score_gci_goi(np.array([250], dtype=np.int64), REF_GCI, FS)
    cyc = _by_index(res.gci.cycles)
    assert cyc[1].detections == ()
    assert cyc[1].outcome is Outcome.MISS
    assert cyc[2].detections == (250,)
    assert cyc[2].outcome is Outcome.IDENTIFICATION
    assert cyc[2].ref_instant == 300
    assert cyc[2].timing_error == pytest.approx(-50.0)  # 250 - 300


def test_detections_outside_scored_cycles_are_not_counted():
    """Estimated instants in the unscored first/last boundary regions are dropped.

    120 (< first cycle lo 150) and 560 (>= last cycle hi 550) fall in the boundary
    half-cycles that the formula leaves unscored; only 300 (in r=2) is counted.
    """
    res = score_gci_goi(np.array([120, 300, 560], dtype=np.int64), REF_GCI, FS)
    cyc = _by_index(res.gci.cycles)
    counted = [d for c in res.gci.cycles for d in c.detections]
    assert counted == [300]  # 120 and 560 counted nowhere
    assert cyc[2].detections == (300,)
    assert cyc[2].outcome is Outcome.IDENTIFICATION
    assert res.gci.n_identification == 1
    assert res.gci.n_miss == 3


def test_all_hits_zero_bias_when_symmetric():
    """Four clean hits; sign convention and aggregation checked on a full sweep."""
    # +2, -2, +2, -2 about each reference GCI -> mean 0, std 2 samples
    est = np.array([202, 298, 402, 498], dtype=np.int64)
    gci = score_gci_goi(est, REF_GCI, FS).gci
    assert gci.n_identification == 4
    assert gci.timing_errors_samples == (2.0, -2.0, 2.0, -2.0)
    assert gci.bias_ms == pytest.approx(0.0)
    assert gci.accuracy_ms == pytest.approx(0.2)  # std 2 samples * 0.1 ms


# --------------------------------------------------------------------------- GOI

REF_GOI = np.array([30, 230, 330, 430, 530, 570], dtype=np.int64)
# one reference GOI inside each interior cycle: 230->r1, 330->r2, 430->r3, 530->r4
# (30 and 570 sit in the unscored boundary regions, as reference GOIs may)


def test_goi_scored_on_gci_cycle_partition_with_accurate_flag():
    """GOI is scored on the GCI-defined cycles; sigma/mu restricted to flagged cycles.

    est_goi = [233, 430, 435, 528] mirrors the GCI pattern: r1 id (zeta=+3, vs GOI
    230), r2 miss, r3 false alarm, r4 id (zeta=-2, vs GOI 530).
    accurate = [False, True, True, True] excludes the r=1 identification from
    sigma/mu, leaving only r=4's zeta=-2.
    """
    est_gci = np.array([203, 498], dtype=np.int64)  # r1, r4 hits (rest miss) - GCI side
    est_goi = np.array([233, 430, 435, 528], dtype=np.int64)
    accurate = np.array([False, True, True, True], dtype=bool)

    res = score_gci_goi(
        est_gci, REF_GCI, FS, est_goi=est_goi, ref_goi=REF_GOI, ref_goi_accurate=accurate
    )
    assert res.goi is not None
    goi = res.goi
    cyc = _by_index(goi.cycles)

    # partition is the GCI one (bounds come from REF_GCI), timing is vs the GOIs
    assert (cyc[1].lo, cyc[1].hi) == (150.0, 250.0)
    assert cyc[1].detections == (233,)
    assert cyc[1].ref_instant == 230  # the GOI in this cycle, not the GCI
    assert cyc[1].outcome is Outcome.IDENTIFICATION
    assert cyc[1].timing_error == pytest.approx(3.0)

    assert cyc[2].outcome is Outcome.MISS
    assert cyc[3].detections == (430, 435)
    assert cyc[3].outcome is Outcome.FALSE_ALARM
    assert cyc[4].ref_instant == 530
    assert cyc[4].timing_error == pytest.approx(-2.0)

    # sigma/mu use only accurate identification cycles: r1 excluded -> only zeta=-2
    assert goi.timing_errors_samples == (-2.0,)
    assert goi.bias_ms == pytest.approx(-0.2)  # -2 samples * 0.1 ms
    assert goi.accuracy_ms == pytest.approx(0.0)  # single value -> std 0

    # GCI hit rate and GOI hit rate are computed independently on the shared partition
    assert res.gci.n_identification == 2
    assert goi.n_identification == 2


def test_goi_without_accurate_flag_omits_sigma_mu_but_reports_rates():
    """Absent the reference-accurate flag, GOI sigma/mu are omitted, never assumed."""
    est_gci = np.array([203, 498], dtype=np.int64)
    est_goi = np.array([233, 528], dtype=np.int64)  # r1, r4 hits
    res = score_gci_goi(est_gci, REF_GCI, FS, est_goi=est_goi, ref_goi=REF_GOI)
    assert res.goi is not None
    assert res.goi.n_identification == 2  # rates still reported
    assert res.goi.id_rate == pytest.approx(50.0)
    assert res.goi.accuracy_ms is None  # sigma omitted
    assert res.goi.bias_ms is None  # mu omitted


def test_goi_absent_entirely_gives_none():
    res = score_gci_goi(np.array([203], dtype=np.int64), REF_GCI, FS)
    assert res.goi is None


def test_goi_needs_both_est_and_ref():
    with pytest.raises(ValueError, match="both est_goi and ref_goi"):
        score_gci_goi(
            np.array([203], dtype=np.int64), REF_GCI, FS, est_goi=np.array([233], dtype=np.int64)
        )


def test_goi_accurate_flag_length_must_match_interior_cycles():
    with pytest.raises(ValueError, match="expected one per interior cycle"):
        score_gci_goi(
            np.array([203], dtype=np.int64),
            REF_GCI,
            FS,
            est_goi=np.array([233], dtype=np.int64),
            ref_goi=REF_GOI,
            ref_goi_accurate=np.array([True, True], dtype=bool),  # 2 != 4 interior cycles
        )


# ---------------------------------------------------------------- input validation


def test_reference_needs_three_instants():
    with pytest.raises(ValueError, match=">= 3"):
        score_gci_goi(np.array([203], dtype=np.int64), np.array([100, 200], dtype=np.int64), FS)


def test_reference_must_be_strictly_increasing():
    with pytest.raises(ValueError, match="strictly increasing"):
        score_gci_goi(
            np.array([203], dtype=np.int64), np.array([100, 300, 200, 400], dtype=np.int64), FS
        )


def test_duplicate_estimates_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        score_gci_goi(np.array([203, 203], dtype=np.int64), REF_GCI, FS)


def test_reference_goi_must_be_one_per_cycle():
    """A cycle with zero or two reference GOIs is a reference/partition inconsistency."""
    bad_ref_goi = np.array([230, 235, 330, 430, 530], dtype=np.int64)  # two in cycle r=1
    with pytest.raises(ValueError, match="expected exactly 1"):
        score_gci_goi(
            np.array([203], dtype=np.int64),
            REF_GCI,
            FS,
            est_goi=np.array([233], dtype=np.int64),
            ref_goi=bad_ref_goi,
        )


def test_std_ddof_is_a_config_convention_not_fitted():
    """The accuracy std convention lives in the explicit config (DESIGN: no globals)."""
    est = np.array([202, 298, 402, 498], dtype=np.int64)  # zeta [+2,-2,+2,-2]
    # population std (ddof=0) of [2,-2,2,-2] = 2.0 samples; sample std (ddof=1) = sqrt(16/3)
    pop = score_gci_goi(est, REF_GCI, FS, config=ScoreConfig(std_ddof=0)).gci
    smp = score_gci_goi(est, REF_GCI, FS, config=ScoreConfig(std_ddof=1)).gci
    assert pop.accuracy_ms == pytest.approx(0.2)
    assert smp.accuracy_ms == pytest.approx(np.sqrt(16.0 / 3.0) / FS * 1000.0)
    assert isinstance(ScoreResult(gci=pop), ScoreResult)
