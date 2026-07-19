"""Resolve reference-tree paths from the environment for the capture scripts.

The reference MATLAB trees these captures run against are private, untested, and
unpublished; their filesystem location is never hardcoded in committed source
(the same rule DESIGN section 5 states for external datasets). Each capture
script reads a role-named environment variable pointing at a reference tree
root and fails loudly -- naming the variable -- when it is unset or does not
resolve to a directory.

The loud failure is load-bearing: there is deliberately **no** silent fallback
to a default path. An unset variable that quietly resolved to a stale local
checkout would let a re-run produce an out-of-date capture that then passes as a
fresh golden -- the exact silent-staleness trap the golden-master discipline
exists to prevent. Unset is an error, not a default.
"""

from __future__ import annotations

import os
from pathlib import Path


def require_reference_dir(var: str, role: str) -> Path:
    """Return the directory named by env var ``var``, or exit with a clear error.

    ``role`` describes what the reference tree provides, for the error message.
    Exits (never returns a fallback) when ``var`` is unset/empty or when its
    value is not an existing directory.
    """
    raw = os.environ.get(var)
    if not raw:
        raise SystemExit(
            f"{var} is not set; point it at {role}. Reference-tree paths are "
            "never hardcoded and have no default -- an unset variable is an "
            "error, not a fallback (see DESIGN section 5)."
        )
    path = Path(raw)
    if not path.is_dir():
        raise SystemExit(f"{var} is set to {path!r}, which is not an existing directory.")
    return path
