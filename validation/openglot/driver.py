"""OpenGlot R1 scoring driver: reference -> detector -> scorer -> report.

Wires the ratified pieces. The estimated-instant path (the part with no gate
behind it) is fixed and narrow:

- the detector reads **channel 0 (speech pressure)** -- YAGA detects GCIs from the
  speech signal; the R1 reference is analytic (OG-GCI-A) and uses no channel, so
  unlike R2 there is no flow-vs-pressure choice on the reference side;
- the detector runs under a caller-supplied `YagaConfig`, defaulting to the
  reference detector (bug-compat quarantine flags on) -- the baseline the faithful
  port scores; the config is serialized into the run_manifest;
- **nothing is added** between detector and scorer: ``est_gci`` is
  ``yaga(...).gcis.gci`` verbatim (0-based int64), scored against the float
  reference. No threshold, refinement, re-selection or coercion.

R1 scores **GCI only**. There is no GOI accuracy section -- not an empty one, not
one with a caveat: the driver never builds GOI metrics (OG-GOI: R1's t_o is a
synthesis seam). The report machinery's provenance requirement guards whatever is
emitted; the GOI absence is structural.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from validation.openglot.reference import R1_FS, reference_gci_train
from validation.openglot.strata import STRATA
from validation.report import Aggregate, Breakdown, QualifiedValue, Report, Standing
from voicekit.eval import InstantScore, score_gci_goi
from voicekit.io import read_wav
from voicekit.signal import Signal
from voicekit.yaga import YagaConfig, yaga

# The channel the detector reads. R1 ships [pressure, flow]; YAGA detects from
# pressure. The reference is analytic, so no channel is read for it.
R1_DETECTOR_CHANNEL = 0

# Every R1 GCI metric is scored against the analytic closed form, so its standing is
# PRIMARY and its ledger reference is the entry that defines that reference.
_R1_GCI_LEDGER = "OG-GCI-A"

Detector = Callable[[Signal, YagaConfig | None], npt.NDArray[np.int64]]


def detect_gci(signal: Signal, config: YagaConfig | None = None) -> npt.NDArray[np.int64]:
    """The estimated-instant path: run YAGA, return its GCIs verbatim (0-based int64)."""
    return yaga(signal, config).gcis.gci


def load_r1_pressure(path: str | Path) -> Signal:
    """Load an R1 file's speech-pressure channel (channel 0) as a `Signal`."""
    return read_wav(path, channel=R1_DETECTOR_CHANNEL)


def score_r1_file(
    pressure: Signal,
    mode: str,
    f0: float,
    *,
    config: YagaConfig | None = None,
    detect: Detector = detect_gci,
) -> InstantScore:
    """Score one R1 file's GCIs against the analytic reference. GCI only, no GOI."""
    est_gci = detect(pressure, config)
    ref = reference_gci_train(mode, f0, pressure.n_samples, float(pressure.fs))
    result = score_gci_goi(est_gci, ref, float(pressure.fs))
    return result.gci


@dataclass(frozen=True)
class R1FileResult:
    """One file's GCI score, tagged with the identity needed to stratify it."""

    relpath: str
    vowel: str
    mode: str
    f0_hz: int
    score: InstantScore


def _pooled_metrics(scores: Sequence[InstantScore], fs: float) -> dict[str, QualifiedValue]:
    """Pool raw per-cycle outcomes and timing errors across files, then compute.

    Never averages per-file summaries -- pools the raw zetas and counts, then derives
    σ/μ/rates (VUV5/VUV11; the `QualifiedValue` guard makes averaging summaries raise).
    The results are wrapped with PRIMARY standing (the analytic reference).
    """
    zetas = (
        np.concatenate([np.asarray(s.timing_errors_samples, dtype=np.float64) for s in scores])
        if scores
        else np.empty(0)
    )
    n_cycles = sum(s.n_cycles for s in scores)
    n_id = sum(s.n_identification for s in scores)
    n_miss = sum(s.n_miss for s in scores)
    n_fa = sum(s.n_false_alarm for s in scores)

    def qv(x: float) -> QualifiedValue:
        return QualifiedValue(x, Standing.PRIMARY, _R1_GCI_LEDGER)

    metrics = {
        "gci_id_rate": qv(100.0 * n_id / n_cycles if n_cycles else 0.0),
        "gci_miss_rate": qv(100.0 * n_miss / n_cycles if n_cycles else 0.0),
        "gci_fa_rate": qv(100.0 * n_fa / n_cycles if n_cycles else 0.0),
    }
    if zetas.size:
        metrics["gci_accuracy_ms"] = qv(float(np.std(zetas)) / fs * 1000.0)
        metrics["gci_bias_ms"] = qv(float(np.mean(zetas)) / fs * 1000.0)
    return metrics


def _breakdown(
    results: Sequence[R1FileResult], axis: str, key: Callable[[R1FileResult], str], fs: float
) -> Breakdown:
    """A same-standing disaggregation of the accuracy along one axis (vowel or f0)."""
    entries: dict[str, QualifiedValue] = {}
    groups: dict[str, list[InstantScore]] = {}
    for r in results:
        groups.setdefault(key(r), []).append(r.score)
    for k in sorted(groups):
        m = _pooled_metrics(groups[k], fs)
        if "gci_accuracy_ms" in m:  # distribution of accuracy, the axis's point
            entries[k] = m["gci_accuracy_ms"]
    return Breakdown(axis=axis, entries=entries)


def aggregate_r1(results: Sequence[R1FileResult], fs: float = R1_FS) -> Report:
    """Stratify per-file results into the ratified report: primary pooled, whispery apart.

    One `Aggregate` per stratum; vowel and f0 as breakdowns (same standing). No GOI
    metrics anywhere -- structurally absent. ``n_distinct_reference_trains`` is the
    count of distinct (mode, f0) pairs, since the flow (and thus the reference) is
    bit-identical across vowels (OG-GCI-D), so vowels do not add reference trains.
    """
    aggs: list[Aggregate] = []
    for stratum in STRATA:
        rows = [r for r in results if r.mode in stratum.members]
        if not rows:
            continue
        distinct_trains = len({(r.mode, r.f0_hz) for r in rows})
        aggs.append(
            Aggregate(
                stratum=stratum,
                members=tuple(sorted({r.mode for r in rows})),
                n_files=len(rows),
                n_distinct_reference_trains=distinct_trains,
                metrics=_pooled_metrics([r.score for r in rows], fs),
                breakdowns=(
                    _breakdown(rows, "vowel", lambda r: r.vowel, fs),
                    _breakdown(rows, "f0", lambda r: str(r.f0_hz), fs),
                ),
            )
        )
    return Report(aggregates=tuple(aggs))
