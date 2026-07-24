"""Command-line entry for OpenGlot corpus operations.

Currently exposes ``--emit-manifest`` -- the one-time manifest generation whose
output is committed and thereafter only verified. The full scoring driver is a
later step; this CLI carries the path-resolution and emission plumbing it needs.

Run: ``python -m validation.openglot.cli --emit-manifest --out PATH [--openglot-root DIR]``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from validation.openglot.loader import (
    emit_r1_manifest,
    resolve_root,
    write_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validation.openglot.cli")
    parser.add_argument(
        "--openglot-root",
        default=None,
        help="OpenGlot root (else $VOICEKIT_OPENGLOT_DIR, else $VOICEKIT_DATA_DIR/openglot)",
    )
    parser.add_argument(
        "--emit-manifest",
        action="store_true",
        help="discover and hash every R1 file, write the manifest (one-time)",
    )
    parser.add_argument("--out", type=Path, default=None, help="manifest output path")
    args = parser.parse_args(argv)

    # resolve_root raises (nonzero exit) when no root is configured -- no silent default.
    resolved = resolve_root(args.openglot_root)

    if args.emit_manifest:
        if args.out is None:
            parser.error("--emit-manifest requires --out PATH")
        rows = emit_r1_manifest(resolved.path)
        write_manifest(rows, args.out)
        n_files = len(rows)
        n_flow = len({r.flow_sha256 for r in rows})
        n_file_hash = len({r.file_sha256 for r in rows})
        print(f"resolved root: {resolved.path} (via {resolved.rule})")
        print(f"wrote {n_files} rows to {args.out}")
        print(f"distinct file hashes: {n_file_hash}   distinct flow hashes: {n_flow}")
        return 0

    parser.error("no operation requested (e.g. --emit-manifest)")
    return 2  # unreachable; parser.error exits


if __name__ == "__main__":
    sys.exit(main())
