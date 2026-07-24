"""OpenGlot corpus loading: path resolution, manifest, run provenance.

Path resolution is treated as load-bearing, not plumbing: the exact set of scored
files must be pinned and recoverable from a result, so there is **no globbing, no
fallback, no search** on the scoring path. The scored set comes from a committed
manifest, emitted once by `emit_r1_manifest` and thereafter only *verified* against
the tree. If the input set cannot be reconstructed from a result, the result is not
reproducible -- so every run emits a `run_manifest` recording exactly what it read.

Layering (REFERENCE_NOTES SCORE2): this loader asserts **corpus-file integrity**
only (hashes, channel count, filename<->manifest agreement). It does not assert
reference *value* structure -- that is the constructor's job
(`reference._assert_phase_invariant`) -- and the scorer asserts neither.

R1 (RepositoryI) is the focus here: 2-channel wav (pressure, glottal flow), 6
vowel folders x 56 (mode, f0) = 336 files, with the flow channel bit-identical
across vowels (OG-GCI-D), so 336 distinct file hashes but only 56 distinct
flow-channel hashes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import wavfile

# --- path resolution -------------------------------------------------------------

# The RepositoryI subtree under the OpenGlot root, and the flow channel index.
R1_SUBTREE = Path("RI") / "RepositoryI"
R1_FLOW_CHANNEL = 1  # channel 0 = speech pressure, channel 1 = glottal flow

_R1_NAME = re.compile(
    r"^(?P<vowel>A|E|I|O|U|AE)_(?P<mode>normal|breathy|creaky|whispery)_(?P<f0>\d+)Hz\.wav$"
)


@dataclass(frozen=True)
class ResolvedRoot:
    """The resolved OpenGlot root and which rule resolved it (both go in output)."""

    path: Path
    rule: str  # human-readable: which precedence rule fired


def resolve_root(
    cli_root: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedRoot:
    """Resolve the OpenGlot root by strict precedence; error if none is configured.

    Precedence, no fallback beyond it: ``cli_root`` (``--openglot-root``), then
    ``$VOICEKIT_OPENGLOT_DIR``, then ``$VOICEKIT_DATA_DIR/openglot``. If none is
    set, raise naming all three (the caller exits nonzero). A configured root that
    does not exist is also an error -- never silently skipped.
    """
    env = os.environ if environ is None else environ
    candidate: Path | None = None
    rule = ""
    if cli_root is not None:
        candidate, rule = Path(cli_root), "--openglot-root"
    elif env.get("VOICEKIT_OPENGLOT_DIR"):
        candidate, rule = Path(env["VOICEKIT_OPENGLOT_DIR"]), "$VOICEKIT_OPENGLOT_DIR"
    elif env.get("VOICEKIT_DATA_DIR"):
        candidate = Path(env["VOICEKIT_DATA_DIR"]) / "openglot"
        rule = "$VOICEKIT_DATA_DIR/openglot"

    if candidate is None:
        raise ValueError(
            "OpenGlot root not configured. Set one of, in precedence order: "
            "--openglot-root PATH, $VOICEKIT_OPENGLOT_DIR, or $VOICEKIT_DATA_DIR "
            "(the loader appends /openglot). No default and no search."
        )
    if not candidate.is_dir():
        raise ValueError(f"OpenGlot root resolved via {rule} does not exist: {candidate}")
    return ResolvedRoot(path=candidate, rule=rule)


# --- filename parse --------------------------------------------------------------


@dataclass(frozen=True)
class R1Meta:
    """Metadata parsed from an R1 filename (cross-checked against the manifest)."""

    vowel: str
    mode: str
    f0_hz: int


def parse_r1_name(filename: str) -> R1Meta:
    """Parse ``<VOWEL>_<mode>_<f0>Hz.wav``; raise on any non-match (never skip)."""
    m = _R1_NAME.match(filename)
    if m is None:
        raise ValueError(f"filename does not match the R1 pattern: {filename!r}")
    return R1Meta(vowel=m["vowel"], mode=m["mode"], f0_hz=int(m["f0"]))


# --- manifest --------------------------------------------------------------------

_MANIFEST_COLUMNS = (
    "relpath",
    "file_sha256",
    "flow_sha256",
    "fs",
    "n_channels",
    "n_samples",
    "vowel",
    "mode",
    "f0_hz",
)


@dataclass(frozen=True)
class R1ManifestRow:
    """One committed manifest row -- the integrity + identity pin for one file.

    ``file_sha256`` pins the whole file; ``flow_sha256`` pins channel 1 alone (what
    is scored), and its distinct-count across the corpus is a check on OG-GCI-D.
    """

    relpath: str
    file_sha256: str
    flow_sha256: str
    fs: int
    n_channels: int
    n_samples: int
    vowel: str
    mode: str
    f0_hz: int


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inspect_file(root: Path, relpath: str) -> R1ManifestRow:
    """Hash and read one R1 file, cross-checking its filename against its contents."""
    path = root / relpath
    file_sha = _sha256_bytes(path.read_bytes())
    fs, data = wavfile.read(path)
    if data.ndim != 2 or data.shape[1] < R1_FLOW_CHANNEL + 1:
        raise ValueError(
            f"{relpath}: expected >= {R1_FLOW_CHANNEL + 1} channels for R1 flow, "
            f"got shape {data.shape}"
        )
    flow = np.ascontiguousarray(data[:, R1_FLOW_CHANNEL])
    flow_sha = _sha256_bytes(flow.tobytes())
    meta = parse_r1_name(path.name)
    return R1ManifestRow(
        relpath=relpath,
        file_sha256=file_sha,
        flow_sha256=flow_sha,
        fs=int(fs),
        n_channels=int(data.shape[1]),
        n_samples=int(data.shape[0]),
        vowel=meta.vowel,
        mode=meta.mode,
        f0_hz=meta.f0_hz,
    )


def emit_r1_manifest(root: Path) -> list[R1ManifestRow]:
    """Discover and inspect every R1 wav under ``root`` -- the ONE-TIME emission.

    This is the only place that walks the tree; the walk is deterministic (sorted)
    and its result is committed as the manifest. Every later run *verifies* against
    that manifest and never walks. A filename that does not parse raises here rather
    than being silently skipped, so the manifest cannot omit a stray file quietly.
    """
    subtree = root / R1_SUBTREE
    if not subtree.is_dir():
        raise ValueError(f"R1 subtree not found under root: {subtree}")
    files = sorted(p.relative_to(root).as_posix() for p in subtree.rglob("*.wav"))
    return [_inspect_file(root, rp) for rp in files]


def write_manifest(rows: list[R1ManifestRow], path: Path) -> None:
    """Write rows as a tab-separated manifest with a header, sorted by relpath."""
    ordered = sorted(rows, key=lambda r: r.relpath)
    lines = ["\t".join(_MANIFEST_COLUMNS)]
    for r in ordered:
        d = asdict(r)
        lines.append("\t".join(str(d[c]) for c in _MANIFEST_COLUMNS))
    path.write_text("\n".join(lines) + "\n")


def read_manifest(path: Path) -> list[R1ManifestRow]:
    """Read a manifest written by `write_manifest`; raise on a malformed header."""
    text = path.read_text().splitlines()
    if not text or text[0].split("\t") != list(_MANIFEST_COLUMNS):
        raise ValueError(f"manifest header mismatch in {path}")
    rows = []
    for line in text[1:]:
        if not line:
            continue
        f = line.split("\t")
        rows.append(
            R1ManifestRow(
                relpath=f[0],
                file_sha256=f[1],
                flow_sha256=f[2],
                fs=int(f[3]),
                n_channels=int(f[4]),
                n_samples=int(f[5]),
                vowel=f[6],
                mode=f[7],
                f0_hz=int(f[8]),
            )
        )
    return rows


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of verifying a tree against a committed manifest."""

    verified: tuple[str, ...]  # relpaths whose file hash matched
    missing: tuple[str, ...]  # relpaths in the manifest absent from the tree


def verify_manifest(
    root: Path, rows: list[R1ManifestRow], *, allow_missing: bool = False
) -> VerifyResult:
    """Verify each manifest row against the tree; hash mismatch always aborts.

    A file present but with a changed hash is a hard error (the scored bytes are not
    what was pinned). A file absent aborts too, unless ``allow_missing`` -- which the
    caller passes explicitly and records in the run_manifest, so a partial run is
    never silent.
    """
    verified: list[str] = []
    missing: list[str] = []
    for r in rows:
        path = root / r.relpath
        if not path.exists():
            missing.append(r.relpath)
            continue
        actual = _sha256_bytes(path.read_bytes())
        if actual != r.file_sha256:
            raise ValueError(
                f"{r.relpath}: file hash mismatch (manifest {r.file_sha256[:12]}..., "
                f"tree {actual[:12]}...); the scored bytes are not the pinned bytes"
            )
        verified.append(r.relpath)
    if missing and not allow_missing:
        raise ValueError(
            f"{len(missing)} manifest file(s) absent from the tree "
            f"(first: {missing[0]}); pass allow_missing to run on a subset"
        )
    return VerifyResult(verified=tuple(verified), missing=tuple(missing))


# --- run provenance --------------------------------------------------------------


def _git_state() -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = (
            subprocess.run(
                ["git", "-C", str(repo), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            != ""
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": dirty}


def build_run_manifest(
    resolved: ResolvedRoot,
    manifest_path: Path,
    rows: list[R1ManifestRow],
    verify: VerifyResult,
    *,
    channel: int,
    allow_missing: bool,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the provenance header that makes a run reconstructible.

    ``channel`` is surfaced at the TOP level (not only inside ``config``): scoring
    the flow vs the pressure channel is the highest-consequence silent-wrong-answer
    in a run, so it must be readable at a glance.
    """
    return {
        "channel": channel,  # top-level by decision (read-at-a-glance)
        "openglot_root": str(resolved.path),
        "resolution_rule": resolved.rule,
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
        "n_manifest_rows": len(rows),
        "n_verified": len(verify.verified),
        "missing": list(verify.missing),
        "allow_missing": allow_missing,
        "scored_files": [
            {"relpath": r.relpath, "file_sha256": r.file_sha256, "flow_sha256": r.flow_sha256}
            for r in rows
            if r.relpath in set(verify.verified)
        ],
        "git": _git_state(),
        "voicekit_config": dict(config),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }


def write_run_manifest(run_manifest: Mapping[str, Any], path: Path) -> None:
    """Serialise a run_manifest as indented JSON (channel readable at the top)."""
    path.write_text(json.dumps(dict(run_manifest), indent=2, sort_keys=False) + "\n")
