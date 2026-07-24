"""R1 scoring driver: the wire-up, tested with an injected detector (no corpus, no YAGA).

The estimated-instant path is fixed and injectable so the wiring -- channel read,
reference build, scoring, stratified aggregation, GOI absence -- is exercised on
synthetic inputs without running the detector or touching the corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile
from validation.openglot.driver import (
    R1FileResult,
    aggregate_r1,
    load_r1_pressure,
    score_r1_file,
)
from validation.openglot.reference import reference_gci_train
from validation.report import Report, Standing, write_report

from voicekit.signal import Signal

FS = 8000.0
N = 1600


def _pressure(n: int = N) -> Signal:
    return Signal(samples=np.zeros(n), fs=int(FS))  # detector is injected; samples unused


def _detector_returning(est: np.ndarray):
    return lambda signal, config: est.astype(np.int64)


def _score_with_offset(mode: str, f0: float, offset: int):
    ref = reference_gci_train(mode, f0, N, FS)
    est = np.round(ref).astype(np.int64) + offset
    return score_r1_file(_pressure(), mode, f0, detect=_detector_returning(est))


# --- channel read ---------------------------------------------------------------


def test_load_reads_channel_zero_the_pressure(tmp_path: Path) -> None:
    ch0 = np.full(64, 3000, dtype=np.int16)  # pressure
    ch1 = np.full(64, -20000, dtype=np.int16)  # flow (must NOT be read)
    wavfile.write(tmp_path / "f.wav", 8000, np.stack([ch0, ch1], axis=1))
    sig = load_r1_pressure(tmp_path / "f.wav")
    assert np.allclose(sig.samples, 3000 / 32768.0)
    assert sig.source.endswith("#ch0")


# --- single-file scoring --------------------------------------------------------


def test_score_one_file_gci_only_no_goi() -> None:
    # est = round(reference): every cycle a hit, uniform sub-sample offset.
    score = _score_with_offset("normal", 140.0, offset=0)
    assert score.n_miss == 0 and score.n_false_alarm == 0
    assert score.id_rate == pytest.approx(100.0)
    # normal@140 has integer period 58, phase 32.5 -> round is -0.5 uniform -> sigma 0
    assert score.accuracy_ms == pytest.approx(0.0, abs=1e-9)
    assert score.bias_ms == pytest.approx(-0.5 / FS * 1000.0)  # -0.0625 ms


def test_score_reflects_a_known_offset() -> None:
    score = _score_with_offset("normal", 140.0, offset=3)
    # zeta = 3 - 0.5 = 2.5 samples uniform -> sigma 0, bias 2.5 samples
    assert score.accuracy_ms == pytest.approx(0.0, abs=1e-9)
    assert score.bias_ms == pytest.approx(2.5 / FS * 1000.0)


# --- stratified aggregation -----------------------------------------------------


def _results() -> list[R1FileResult]:
    out = []
    # modal trio across two vowels at one f0 (so distinct trains < files), plus whispery.
    for vowel in ("E", "A"):
        for mode in ("normal", "breathy", "creaky", "whispery"):
            score = _score_with_offset(mode, 140.0, offset=2)
            out.append(R1FileResult(f"{vowel}_{mode}", vowel, mode, 140, score))
    return out


def test_aggregate_splits_primary_and_whispery() -> None:
    report = aggregate_r1(_results())
    by_name = {a.stratum.name: a for a in report.aggregates}
    assert set(by_name) == {"primary", "whispery"}
    assert set(by_name["primary"].members) == {"normal", "breathy", "creaky"}
    assert by_name["whispery"].members == ("whispery",)
    # primary pools the trio over 2 vowels = 6 files but only 3 distinct reference trains
    assert by_name["primary"].n_files == 6
    assert by_name["primary"].n_distinct_reference_trains == 3
    assert by_name["whispery"].n_files == 2
    assert by_name["whispery"].n_distinct_reference_trains == 1


def test_metrics_carry_primary_standing_and_ledger_ref() -> None:
    report = aggregate_r1(_results())
    prim = next(a for a in report.aggregates if a.stratum.name == "primary")
    acc = prim.metrics["gci_accuracy_ms"]
    assert acc.standing is Standing.PRIMARY
    assert acc.ledger_ref == "OG-GCI-A"


def test_report_has_no_goi_section_anywhere(tmp_path: Path) -> None:
    report = aggregate_r1(_results())
    out = tmp_path / "r.json"
    write_report(report, out)
    text = out.read_text().lower()
    assert "goi" not in text  # structurally absent, not an empty/caveated section
    loaded = json.loads(out.read_text())
    for agg in loaded["aggregates"]:
        assert all(k.startswith("gci_") for k in agg["metrics"])


def test_breakdowns_are_present_for_vowel_and_f0() -> None:
    report = aggregate_r1(_results())
    prim = next(a for a in report.aggregates if a.stratum.name == "primary")
    axes = {bd.axis for bd in prim.breakdowns}
    assert axes == {"vowel", "f0"}
    vowel_bd = next(bd for bd in prim.breakdowns if bd.axis == "vowel")
    assert set(vowel_bd.entries) == {"E", "A"}  # same standing, distribution only


def test_write_report_round_trips_the_full_r1_report(tmp_path: Path) -> None:
    report = aggregate_r1(_results())
    out = tmp_path / "r.json"
    write_report(report, out)
    loaded = json.loads(out.read_text())
    assert {a["stratum"] for a in loaded["aggregates"]} == {"primary", "whispery"}
    assert isinstance(report, Report)
