"""Resolve external reference paths from the environment for the capture scripts.

Every path a capture script needs to a machine-specific referent -- the private
reference MATLAB trees, the public VOICEBOX toolbox checkout, the MATLAB
executable -- is read from a role-named environment variable and never hardcoded
in committed source (the same rule DESIGN section 5 states for external
datasets). Each resolver fails loudly -- naming the variable -- when it is unset
or does not resolve to the expected kind of path.

The loud failure is load-bearing, and it is not only about privacy: there is
deliberately **no** silent fallback to a default path for *any* of these. An
unset variable that quietly resolved to a stale or wrong local checkout would
let a re-run produce an out-of-date capture that then passes as a fresh golden
-- the silent-staleness trap the golden-master discipline exists to prevent,
which applies to public referents (VOICEBOX, MATLAB) exactly as to private
trees. And a hardcoded ``/Users/...`` default would ship one author's filesystem
layout in a public repo, broken-by-default for everyone else. Unset is an error,
not a default.
"""

from __future__ import annotations

import os
from pathlib import Path


def _require_env_path(var: str, role: str) -> Path:
    """Return the path named by env var ``var``, or exit if it is unset/empty."""
    raw = os.environ.get(var)
    if not raw:
        raise SystemExit(
            f"{var} is not set; point it at {role}. Reference paths are never "
            "hardcoded and have no default -- an unset variable is an error, not "
            "a fallback (see DESIGN section 5)."
        )
    return Path(raw)


def require_reference_dir(var: str, role: str) -> Path:
    """Return the directory named by env var ``var``, or exit with a clear error.

    ``role`` describes what the referent provides, for the error message. Exits
    (never returns a fallback) when ``var`` is unset/empty or when its value is
    not an existing directory.
    """
    path = _require_env_path(var, role)
    if not path.is_dir():
        raise SystemExit(f"{var} is set to {path!r}, which is not an existing directory.")
    return path


def require_reference_file(var: str, role: str) -> Path:
    """Return the file named by env var ``var``, or exit with a clear error.

    For referents that are a file rather than a directory (e.g. the MATLAB
    executable). ``role`` describes the referent, for the error message. Exits
    (never returns a fallback) when ``var`` is unset/empty or when its value is
    not an existing file.
    """
    path = _require_env_path(var, role)
    if not path.is_file():
        raise SystemExit(f"{var} is set to {path!r}, which is not an existing file.")
    return path
