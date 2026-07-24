"""OpenGlot loader: resolution, parse, manifest, verification, run provenance.

All on tiny synthetic wavs in tmp_path -- no corpus needed, runs in default CI.
The committed R1 manifest is emitted separately from the real corpus.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile
from validation.openglot.loader import (
    R1_SUBTREE,
    build_run_manifest,
    emit_r1_manifest,
    parse_r1_name,
    read_manifest,
    resolve_root,
    verify_manifest,
    write_manifest,
    write_run_manifest,
)

# --- a tiny synthetic R1 tree ---------------------------------------------------


def _write_r1_file(root: Path, vowel: str, mode: str, f0: int, flow: np.ndarray) -> str:
    d = root / R1_SUBTREE / f"Vowel_{vowel}"
    d.mkdir(parents=True, exist_ok=True)
    # Pressure differs by vowel (the vocal-tract filter differs), flow does not --
    # mirroring OG-GCI-D: distinct file hashes, shared flow hash across vowels.
    pressure = ((np.arange(flow.size) + ord(vowel[0])) % 7).astype(np.int16)
    stereo = np.stack([pressure, flow.astype(np.int16)], axis=1)
    name = f"{vowel}_{mode}_{f0}Hz.wav"
    wavfile.write(d / name, 8000, stereo)
    return (R1_SUBTREE / f"Vowel_{vowel}" / name).as_posix()


def _tiny_corpus(root: Path) -> list[str]:
    # two vowels share ONE flow signal (bit-identical), two files total.
    flow = (np.arange(40) % 5).astype(np.int16)
    return [
        _write_r1_file(root, "E", "normal", 140, flow),
        _write_r1_file(root, "A", "normal", 140, flow),  # same flow, different pressure
    ]


# --- resolution -----------------------------------------------------------------


class TestResolveRoot:
    def test_raises_when_no_root_configured(self) -> None:
        # The guard: the entry point raises loudly rather than defaulting.
        with pytest.raises(ValueError, match="not configured"):
            resolve_root(None, environ={})

    def test_cli_root_wins(self, tmp_path: Path) -> None:
        r = resolve_root(str(tmp_path), environ={"VOICEKIT_OPENGLOT_DIR": "/nope"})
        assert r.path == tmp_path
        assert r.rule == "--openglot-root"

    def test_openglot_env_before_data_dir(self, tmp_path: Path) -> None:
        env = {"VOICEKIT_OPENGLOT_DIR": str(tmp_path), "VOICEKIT_DATA_DIR": "/nope"}
        r = resolve_root(None, environ=env)
        assert r.path == tmp_path
        assert r.rule == "$VOICEKIT_OPENGLOT_DIR"

    def test_data_dir_appends_openglot(self, tmp_path: Path) -> None:
        (tmp_path / "openglot").mkdir()
        r = resolve_root(None, environ={"VOICEKIT_DATA_DIR": str(tmp_path)})
        assert r.path == tmp_path / "openglot"
        assert r.rule == "$VOICEKIT_DATA_DIR/openglot"

    def test_configured_but_missing_root_raises(self) -> None:
        with pytest.raises(ValueError, match="does not exist"):
            resolve_root("/definitely/not/here")


# --- filename parse -------------------------------------------------------------


class TestParse:
    def test_parses_known_names(self) -> None:
        m = parse_r1_name("AE_breathy_300Hz.wav")
        assert (m.vowel, m.mode, m.f0_hz) == ("AE", "breathy", 300)

    @pytest.mark.parametrize(
        "bad",
        [
            "E_normal_140.wav",  # missing Hz
            "E_shouty_140Hz.wav",  # unknown mode
            "E_normal_140Hz.flac",  # wrong ext
            "Vowel_E.wav",  # not a data file
        ],
    )
    def test_raises_on_non_match(self, bad: str) -> None:
        with pytest.raises(ValueError, match="does not match"):
            parse_r1_name(bad)


# --- manifest emit / round-trip / cross-check -----------------------------------


class TestManifest:
    def test_emit_inspects_every_file_and_parses_metadata(self, tmp_path: Path) -> None:
        rels = _tiny_corpus(tmp_path)
        rows = emit_r1_manifest(tmp_path)
        assert {r.relpath for r in rows} == set(rels)
        assert all(r.n_channels == 2 and r.fs == 8000 for r in rows)
        # flow bit-identical across the two vowels -> 1 distinct flow hash, 2 file hashes
        assert len({r.flow_sha256 for r in rows}) == 1
        assert len({r.file_sha256 for r in rows}) == 2

    def test_emit_raises_on_unparseable_filename(self, tmp_path: Path) -> None:
        _tiny_corpus(tmp_path)
        stray = tmp_path / R1_SUBTREE / "Vowel_E" / "E_normal_140.wav"  # no Hz
        wavfile.write(stray, 8000, np.zeros((10, 2), dtype=np.int16))
        with pytest.raises(ValueError, match="does not match"):
            emit_r1_manifest(tmp_path)

    def test_round_trip(self, tmp_path: Path) -> None:
        _tiny_corpus(tmp_path)
        rows = emit_r1_manifest(tmp_path)
        out = tmp_path / "manifest.tsv"
        write_manifest(rows, out)
        back = read_manifest(out)
        assert sorted(back, key=lambda r: r.relpath) == sorted(rows, key=lambda r: r.relpath)

    def test_read_rejects_bad_header(self, tmp_path: Path) -> None:
        p = tmp_path / "m.tsv"
        p.write_text("wrong\theader\n")
        with pytest.raises(ValueError, match="header mismatch"):
            read_manifest(p)


# --- verification ---------------------------------------------------------------


class TestVerify:
    def test_all_present_verifies(self, tmp_path: Path) -> None:
        _tiny_corpus(tmp_path)
        rows = emit_r1_manifest(tmp_path)
        res = verify_manifest(tmp_path, rows)
        assert set(res.verified) == {r.relpath for r in rows}
        assert res.missing == ()

    def test_hash_mismatch_always_aborts(self, tmp_path: Path) -> None:
        rels = _tiny_corpus(tmp_path)
        rows = emit_r1_manifest(tmp_path)
        # corrupt one file's bytes
        p = tmp_path / rels[0]
        wavfile.write(p, 8000, np.ones((40, 2), dtype=np.int16))
        with pytest.raises(ValueError, match="hash mismatch"):
            verify_manifest(tmp_path, rows)

    def test_missing_aborts_unless_allowed(self, tmp_path: Path) -> None:
        rels = _tiny_corpus(tmp_path)
        rows = emit_r1_manifest(tmp_path)
        (tmp_path / rels[0]).unlink()
        with pytest.raises(ValueError, match="absent from the tree"):
            verify_manifest(tmp_path, rows)
        res = verify_manifest(tmp_path, rows, allow_missing=True)
        assert res.missing == (rels[0],)


# --- run provenance -------------------------------------------------------------


def test_run_manifest_surfaces_channel_at_top_and_pins_the_input_set(tmp_path: Path) -> None:
    _tiny_corpus(tmp_path)
    rows = emit_r1_manifest(tmp_path)
    mpath = tmp_path / "manifest.tsv"
    write_manifest(rows, mpath)
    resolved = resolve_root(str(tmp_path), environ={})
    verify = verify_manifest(tmp_path, rows)

    rm = build_run_manifest(
        resolved, mpath, rows, verify, channel=1, allow_missing=False, config={"std_ddof": 0}
    )
    # channel is a top-level key, not buried in config
    assert rm["channel"] == 1
    assert "channel" not in rm["voicekit_config"]
    # the input set is reconstructible: root, rule, manifest hash, per-file hashes
    assert rm["resolution_rule"] == "--openglot-root"
    assert rm["manifest_sha256"]
    assert {f["relpath"] for f in rm["scored_files"]} == {r.relpath for r in rows}
    assert all("flow_sha256" in f for f in rm["scored_files"])

    out = tmp_path / "run_manifest.json"
    write_run_manifest(rm, out)
    reloaded = json.loads(out.read_text())
    # channel is the first key in the serialised file (read-at-a-glance)
    assert next(iter(reloaded)) == "channel"


def test_committed_r1_manifest_matches_the_predicted_corpus_structure() -> None:
    """The committed R1 manifest (no corpus needed) pins the emission's counts.

    Emitted once against the real corpus; these are the numbers the reviewer's
    watch predicted from the structure (336 files, 336 distinct file hashes, 56
    distinct flow hashes per OG-GCI-D's bit-identical-flow-across-vowels finding,
    6 vowels x 4 modes x 14 f0). If a later regeneration or a corrupted checkout
    changes any of them, this fails without touching the corpus.
    """
    manifest = Path(__file__).resolve().parents[2] / "validation/openglot/manifest_r1.tsv"
    rows = read_manifest(manifest)
    assert len(rows) == 336
    assert len({r.file_sha256 for r in rows}) == 336
    assert len({r.flow_sha256 for r in rows}) == 56  # OG-GCI-D
    assert sorted({r.vowel for r in rows}) == ["A", "AE", "E", "I", "O", "U"]
    assert sorted({r.mode for r in rows}) == ["breathy", "creaky", "normal", "whispery"]
    assert sorted({r.f0_hz for r in rows}) == list(range(100, 361, 20))
    assert all(r.fs == 8000 and r.n_channels == 2 and r.n_samples == 1600 for r in rows)


def test_run_manifest_records_git_state_shape() -> None:
    rm = build_run_manifest(
        resolve_root(".", environ={}),
        Path("pyproject.toml"),  # any existing file, for the sha
        [],
        __import__("validation.openglot.loader", fromlist=["VerifyResult"]).VerifyResult((), ()),
        channel=1,
        allow_missing=False,
        config={},
    )
    assert set(rm["git"]) == {"commit", "dirty"}
