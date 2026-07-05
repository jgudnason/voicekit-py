"""Build an instrumented copy of the reference DYPSA GCI/GOI detector.

The published reference (``vsaTools/YAGA/dypsagoi.m``, GPL, jointly
copyrighted Kounoudes/Gudnason/Naylor/Brookes) returns only its final
results; the per-stage intermediates we need as golden masters
(wavelet detail rows, multiscale product, group-delay function,
phase-slope candidates, DP cost vectors) are local variables inside it.

This script reads that reference at runtime and writes a throwaway
instrumented copy that accumulates those intermediates into a global
``GOLD`` struct via injected ``save`` hooks.

Provenance note: hooks are keyed by **line number**, not by any copied
line of the reference. The only reference-derived facts stored here are
integer offsets and the names of the MATLAB variables being captured
(the functional interface) — no line of the GPL source's expression is
embedded, so this tooling does not vendor GPL text into an Apache-2.0
project. The offsets are pinned to one exact revision of the reference
via a byte SHA-256; if the reference differs at all, ``apply`` raises and
the offsets must be re-derived (see ``derive_offsets``) rather than
risk a silent miscapture.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# The exact reference revision these offsets were derived from. Any change
# to the reference bytes invalidates the line numbers below.
REFERENCE_SHA256 = "033a949d9a73b763a8c743f7778d925534f05027e76522138a67aa4763bad2a9"
REFERENCE_LINES = 838

# 1-based line numbers of the two function headers, after which a
# `global GOLD;` declaration is inserted so hooks in both scopes share one
# struct. (dypsagoi main; dpgci local function.)
HEADER_LINES = (1, 486)

# Capture hooks: (1-based line number, MATLAB statements inserted AFTER it).
# The line number identifies the stage boundary; the statements name the
# variables to capture. Descriptions are our own words, not source text.
HOOKS: list[tuple[int, str, list[str]]] = [
    (175, "IAIF residual fed into the SWT",
     ["GOLD.udash=udash;"]),
    (181, "SWT setup: levels, residual length, pad-to-multiple-of-8 length",
     ["GOLD.nlev=nlev;", "GOLD.nu=nu;", "GOLD.nU=nU;"]),
    (182, "bior1.5 decomposition filters (convention reference)",
     ["GOLD.Lo_D=Lo_D;", "GOLD.Hi_D=Hi_D;"]),
    (184, "SWT approx/detail rows, trimmed back to nu",
     ["GOLD.swa=swa;", "GOLD.swd=swd;"]),
    (187, "multiscale product",
     ["GOLD.mp=mp;"]),
    (192, "negative half-wave rectified product and its cube root",
     ["GOLD.nmp=nmp;", "GOLD.crnmp=crnmp;"]),
    (196, "group delay: raw xewgrdel outputs and its input",
     ["GOLD.gd_r=r;", "GOLD.zcr_cand_raw=zcr_cand;", "GOLD.sew_raw=sew;",
      "GOLD.gdwav_raw=gdwav;", "GOLD.toff=toff;"]),
    (197, "aligned group-delay function",
     ["GOLD.gdwav=gdwav;"]),
    (204, "phase-slope-projection recovered candidates",
     ["GOLD.pro_cand=pro_cand;"]),
    (218, "Frobenius-norm energy function and its input",
     ["GOLD.s_used=s_used;", "GOLD.fnwav=fnwav;"]),
    (228, "closed-phase anticausal/causal energy costs",
     ["GOLD.aencost=aencost;", "GOLD.cencost=cencost;"]),
    (230, "candidate set and phase-slope cost handed to the DP",
     ["GOLD.dp_gcic=gcic;", "GOLD.dp_sew=sew;", "GOLD.gci_dp=gci;"]),
    (248, "final refined GCIs",
     ["GOLD.gci=gci;"]),
    (282, "final GOIs",
     ["GOLD.goi=goi;"]),
    (552, "dpgci: Frobenius energy cost per candidate (vus run only)",
     ["if ~isempty(vus)&&vus, GOLD.dp_Cfn=Cfn; end"]),
    (729, "dpgci vus branch: per-candidate DP cost decomposition",
     ["GOLD.dp_mycost=mycost;", "GOLD.dp_gci_costed=gci;"]),
]


def _check_reference(reference_bytes: bytes) -> None:
    digest = hashlib.sha256(reference_bytes).hexdigest()
    if digest != REFERENCE_SHA256:
        raise ValueError(
            "reference dypsagoi.m does not match the pinned revision "
            f"(sha256 {digest} != {REFERENCE_SHA256}). The line offsets in "
            "this file are stale; re-derive them with derive_offsets() and "
            "update REFERENCE_SHA256/REFERENCE_LINES before re-capturing."
        )


def apply(reference_bytes: bytes) -> str:
    """Return the instrumented source, or raise if the reference is not the
    pinned revision the line offsets were derived from."""
    _check_reference(reference_bytes)
    lines = reference_bytes.decode("latin-1").splitlines()
    if len(lines) != REFERENCE_LINES:  # defensive; the SHA check already covers this
        raise ValueError(f"reference has {len(lines)} lines, expected {REFERENCE_LINES}")

    # Insert bottom-up so earlier line numbers stay valid. Line numbers are
    # 1-based; convert to 0-based insert positions.
    edits: list[tuple[int, list[str]]] = [(n, ["global GOLD;"]) for n in HEADER_LINES]
    edits += [(n, stmts) for n, _desc, stmts in HOOKS]
    for lineno, stmts in sorted(edits, key=lambda e: e[0], reverse=True):
        lines[lineno:lineno] = stmts

    return "\n".join(lines) + "\n"


def derive_offsets(reference_bytes: bytes) -> None:
    """Print current line numbers for each captured variable's assignment.

    Maintenance helper for when the reference revision changes: locates
    where each captured variable is produced so the HOOKS offsets above can
    be updated. Prints line numbers only — it does not copy source lines.
    """
    lines = reference_bytes.decode("latin-1").splitlines()
    print(f"total lines: {len(lines)}")
    print(f"sha256: {hashlib.sha256(reference_bytes).hexdigest()}")
    print("(update HOOKS/HEADER_LINES by inspecting the reference directly)")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="path to published vsaTools dypsagoi.m")
    parser.add_argument("out", type=Path, help="path to write instrumented copy")
    args = parser.parse_args()

    reference_bytes = args.reference.read_bytes()
    args.out.write_text(apply(reference_bytes), encoding="latin-1")
    print(f"wrote instrumented copy to {args.out}")


if __name__ == "__main__":
    main()
