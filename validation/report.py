"""Reporting machinery that carries standing structurally, not in prose.

Three ratified requirements, each a structural carrier so a number can never be
read, pasted, or aggregated in a way that sheds where it came from:

- `QualifiedValue` wraps every reported metric with its **standing** (reference
  authority) and a **ledger reference**. It renders the standing into its string
  form, and it deliberately has **no** ``__float__`` -- so ``float()``, ``sum()``
  and ``np.mean`` over qualified values *raise* rather than silently producing an
  aggregate that has lost its provenance (the VUV5/VUV11 never-aggregate rule, made
  mechanical). REFERENCE_NOTES OG-GOI-E is the motivating case: R2's GOI σ/μ carry
  a biased reference and must not be poolable with a genuine value.

- `Stratum` / `Breakdown` are a **typed distinction**. A stratum changes what a
  number *means* -- its members are never pooled with another stratum's (whispery,
  a weak-excitation stratum, vs the modal trio). A breakdown only *shows the
  distribution* along an axis (vowel, f0) at the same standing. Different types, so
  a call site cannot silently interchange them.

- `Aggregate` requires ``n_files`` and ``n_distinct_reference_trains`` on every
  aggregate (OG-GCI-D: R1 is 56 reference trains x 6 vowels, so a file count
  inflates N by 6x for anything reference-driven), enforces that every metric is a
  `QualifiedValue` (no bare number), and raises if its pooled members escape its
  declared stratum. `write_report` re-checks both, independently of construction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Standing(StrEnum):
    """Reference authority of a reported metric -- orthogonal to stratum membership."""

    PRIMARY = "primary"  # genuine reference (e.g. R1 GCI analytic t_e)
    BIASED_REFERENCE_UNQUANTIFIED = "biased_reference_unquantified"  # R2 GOI (OG-GOI-E)


@dataclass(frozen=True)
class QualifiedValue:
    """A metric value inseparable from its standing and ledger reference.

    ``__float__`` is **intentionally not implemented**: aggregating across the
    primary/stratum boundary is the one operation that would strip standing
    silently, so ``float(qv)``, ``qv + qv``, ``sum(...)`` and ``np.mean(...)`` all
    raise ``TypeError``. To use the raw number deliberately, read ``.value``.
    """

    value: float
    standing: Standing
    ledger_ref: str

    def __format__(self, spec: str) -> str:
        rendered = format(self.value, spec) if spec else f"{self.value:.4g}"
        return f"{rendered} [{self.standing.value}: {self.ledger_ref}]"

    def __str__(self) -> str:
        return self.__format__("")

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.value, "standing": self.standing.value, "ledger_ref": self.ledger_ref}


@dataclass(frozen=True)
class Stratum:
    """A reporting group whose numbers have their own standing and are never pooled
    with another stratum's. ``members`` is the full membership (e.g. the modal trio)."""

    name: str
    members: tuple[str, ...]
    standing: Standing


@dataclass(frozen=True)
class Breakdown:
    """A same-standing disaggregation along one axis (vowel, f0) -- distribution only.

    Not a stratum: it does not change what the numbers mean, so its entries share
    the parent's standing and are shown for shape, never as a separate register.
    """

    axis: str
    entries: Mapping[str, QualifiedValue]


def _require_standing(metrics: Mapping[str, Any]) -> None:
    """Raise unless every metric is a `QualifiedValue` (no bare, provenance-less number)."""
    for name, value in metrics.items():
        if not isinstance(value, QualifiedValue):
            raise ValueError(
                f"metric {name!r} emitted without declared standing "
                f"(got {type(value).__name__}, expected QualifiedValue)"
            )


@dataclass(frozen=True)
class Aggregate:
    """Metrics over a pooled set of members within a single stratum.

    ``n_files`` and ``n_distinct_reference_trains`` are required (no defaults):
    every aggregate must state both so a reference-driven N is never silently
    inflated by vowel replication (OG-GCI-D).
    """

    stratum: Stratum
    members: tuple[str, ...]  # the members actually pooled (subset of stratum.members)
    n_files: int
    n_distinct_reference_trains: int
    metrics: Mapping[str, QualifiedValue]
    breakdowns: tuple[Breakdown, ...] = ()

    def __post_init__(self) -> None:
        _require_standing(self.metrics)
        outside = [m for m in self.members if m not in self.stratum.members]
        if outside:
            raise ValueError(
                f"aggregate pools members {outside} outside its declared stratum "
                f"{self.stratum.name!r} (members {self.stratum.members}) -- strata are "
                "never pooled"
            )
        for bd in self.breakdowns:
            _require_standing(bd.entries)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stratum": self.stratum.name,
            "standing": self.stratum.standing.value,
            "members": list(self.members),
            "n_files": self.n_files,
            "n_distinct_reference_trains": self.n_distinct_reference_trains,
            "metrics": {k: v.as_dict() for k, v in self.metrics.items()},
            "breakdowns": [
                {"axis": bd.axis, "entries": {k: v.as_dict() for k, v in bd.entries.items()}}
                for bd in self.breakdowns
            ],
        }


@dataclass(frozen=True)
class Report:
    """A stratified report: a set of aggregates, no two strata overlapping in members."""

    aggregates: tuple[Aggregate, ...]
    meta: Mapping[str, Any] = field(default_factory=dict)


def write_report(report: Report, path: Path) -> None:
    """Serialise a report as JSON after re-checking standing and stratum separation.

    Independent of `Aggregate.__post_init__`: even if an aggregate were constructed
    by a path that bypassed its validation, the writer refuses to emit a bare metric
    or two aggregates whose strata share a member.
    """
    seen: dict[str, str] = {}  # member -> stratum name
    for agg in report.aggregates:
        _require_standing(agg.metrics)
        for bd in agg.breakdowns:
            _require_standing(bd.entries)
        for m in agg.stratum.members:
            if m in seen and seen[m] != agg.stratum.name:
                raise ValueError(
                    f"member {m!r} appears in two strata ({seen[m]!r} and "
                    f"{agg.stratum.name!r}) -- a mixed strata field"
                )
            seen[m] = agg.stratum.name
    payload = {
        "meta": dict(report.meta),
        "aggregates": [agg.as_dict() for agg in report.aggregates],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
