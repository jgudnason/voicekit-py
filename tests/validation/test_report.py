"""Standing machinery: QualifiedValue, stratum/breakdown, aggregate provenance.

The centrepiece is that QualifiedValue cannot be aggregated silently -- float(),
sum() and np.mean() must raise, because aggregation across the primary/stratum
boundary is the single operation that would strip standing without a trace.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np
import pytest
from validation.report import (
    Aggregate,
    Breakdown,
    QualifiedValue,
    Report,
    Standing,
    Stratum,
    write_report,
)

PRIMARY = Stratum("primary", ("normal", "breathy", "creaky"), Standing.PRIMARY)
WHISPERY = Stratum("whispery", ("whispery",), Standing.PRIMARY)


def _qv(x: float, standing: Standing = Standing.PRIMARY) -> QualifiedValue:
    return QualifiedValue(x, standing, "SCORE2")


class TestQualifiedValueCannotBeAggregated:
    """The load-bearing guard: no silent path from qualified values to a bare mean."""

    def test_float_raises(self) -> None:
        with pytest.raises(TypeError):
            float(_qv(0.213))

    def test_addition_raises(self) -> None:
        with pytest.raises(TypeError):
            _ = _qv(0.2) + _qv(0.3)  # type: ignore[operator]

    def test_sum_raises(self) -> None:
        with pytest.raises(TypeError):
            sum([_qv(0.2), _qv(0.3)])

    def test_numpy_mean_raises(self) -> None:
        arr = np.array([_qv(0.2), _qv(0.3)], dtype=object)
        with pytest.raises(TypeError):
            np.mean(arr)

    def test_value_is_reachable_deliberately(self) -> None:
        # The escape hatch is explicit: read .value when you mean to.
        assert _qv(0.213).value == pytest.approx(0.213)


class TestQualifiedValueRendersStanding:
    def test_str_carries_standing_and_ledger_ref(self) -> None:
        s = str(QualifiedValue(0.213, Standing.BIASED_REFERENCE_UNQUANTIFIED, "OG-GOI-E"))
        assert "biased_reference_unquantified" in s
        assert "OG-GOI-E" in s
        assert "0.213" in s

    def test_format_spec_is_honoured(self) -> None:
        assert format(_qv(0.5), ".2f").startswith("0.50 [")


class TestAggregateProvenanceAndStrata:
    def test_bare_metric_is_a_hard_failure(self) -> None:
        with pytest.raises(ValueError, match="without declared standing"):
            Aggregate(
                PRIMARY,
                ("normal",),
                n_files=84,
                n_distinct_reference_trains=42,
                metrics={"accuracy_ms": 0.2},
            )  # type: ignore[dict-item]

    def test_pooling_a_primary_mode_with_whispery_raises(self) -> None:
        with pytest.raises(ValueError, match="outside its declared stratum"):
            Aggregate(
                PRIMARY,
                ("normal", "whispery"),
                n_files=1,
                n_distinct_reference_trains=1,
                metrics={"accuracy_ms": _qv(0.2)},
            )

    def test_n_files_and_distinct_trains_are_required(self) -> None:
        # Both are non-default fields: omitting either is a construction error.
        with pytest.raises(TypeError):
            Aggregate(PRIMARY, ("normal",), metrics={"accuracy_ms": _qv(0.2)})  # type: ignore[call-arg]

    def test_breakdown_entries_also_require_standing(self) -> None:
        bad = Breakdown(axis="vowel", entries={"A": 0.2})  # type: ignore[dict-item]
        with pytest.raises(ValueError, match="without declared standing"):
            Aggregate(
                PRIMARY,
                ("normal",),
                n_files=84,
                n_distinct_reference_trains=42,
                metrics={"accuracy_ms": _qv(0.2)},
                breakdowns=(bad,),
            )

    def test_valid_aggregate_records_both_counts(self) -> None:
        agg = Aggregate(
            PRIMARY,
            ("normal", "breathy", "creaky"),
            n_files=252,
            n_distinct_reference_trains=42,
            metrics={"accuracy_ms": _qv(0.2)},
        )
        assert agg.n_files == 252
        assert agg.n_distinct_reference_trains == 42


class TestReportWriter:
    def test_writes_and_round_trips_standing(self, tmp_path: Path) -> None:
        agg = Aggregate(
            PRIMARY,
            ("normal",),
            n_files=84,
            n_distinct_reference_trains=14,
            metrics={"accuracy_ms": _qv(0.2)},
        )
        out = tmp_path / "report.json"
        write_report(Report((agg,)), out)
        loaded = json.loads(out.read_text())
        m = loaded["aggregates"][0]["metrics"]["accuracy_ms"]
        assert m["standing"] == "primary" and m["ledger_ref"] == "SCORE2"
        assert loaded["aggregates"][0]["n_distinct_reference_trains"] == 14

    def test_writer_independently_rejects_a_bypassed_bare_metric(self, tmp_path: Path) -> None:
        # Simulate an aggregate whose validation was bypassed (object.__setattr__ on a
        # frozen dataclass): the writer must still refuse to emit a bare metric.
        agg = Aggregate(
            PRIMARY,
            ("normal",),
            n_files=84,
            n_distinct_reference_trains=14,
            metrics={"accuracy_ms": _qv(0.2)},
        )
        object.__setattr__(agg, "metrics", {"accuracy_ms": 0.2})
        with pytest.raises(ValueError, match="without declared standing"):
            write_report(Report((agg,)), tmp_path / "r.json")

    def test_writer_rejects_a_member_in_two_strata(self, tmp_path: Path) -> None:
        overlap = Stratum("shadow", ("normal",), Standing.PRIMARY)  # 'normal' also in PRIMARY
        a1 = Aggregate(
            PRIMARY, ("normal",), n_files=1, n_distinct_reference_trains=1, metrics={"m": _qv(0.1)}
        )
        a2 = Aggregate(
            overlap, ("normal",), n_files=1, n_distinct_reference_trains=1, metrics={"m": _qv(0.1)}
        )
        with pytest.raises(ValueError, match="two strata"):
            write_report(Report((a1, a2)), tmp_path / "r.json")


def test_qualified_value_is_frozen() -> None:
    qv = _qv(0.2)
    with pytest.raises(FrozenInstanceError):
        qv.value = 0.3  # type: ignore[misc]
