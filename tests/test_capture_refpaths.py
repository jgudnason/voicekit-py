"""Pin the loud-failure contract of the capture scripts' path resolver.

``require_reference_dir`` is the single source of the "reference-tree paths come
from the environment, never a hardcoded default" rule the capture scripts share.
The load-bearing property is the *loud failure*: an unset variable must raise a
clear error naming the variable, never fall back to a stale default and let a
capture pass off out-of-date output as fresh. That property is what this pins.

The resolver lives under the (non-package) golden-capture directory, so it is
loaded by file path rather than imported.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REFPATHS = Path(__file__).resolve().parent / "golden" / "capture" / "refpaths.py"
_spec = importlib.util.spec_from_file_location("refpaths", _REFPATHS)
assert _spec is not None and _spec.loader is not None
refpaths = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(refpaths)

_VAR = "VOICEKIT_TEST_REFERENCE_DIR"


def test_unset_raises_naming_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_VAR, raising=False)
    with pytest.raises(SystemExit, match=f"{_VAR} is not set"):
        refpaths.require_reference_dir(_VAR, "the reference tree")


def test_empty_is_treated_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_VAR, "")
    with pytest.raises(SystemExit, match=f"{_VAR} is not set"):
        refpaths.require_reference_dir(_VAR, "the reference tree")


def test_nonexistent_dir_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(_VAR, str(tmp_path / "does_not_exist"))
    with pytest.raises(SystemExit, match="not an existing directory"):
        refpaths.require_reference_dir(_VAR, "the reference tree")


def test_valid_dir_returned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(_VAR, str(tmp_path))
    assert refpaths.require_reference_dir(_VAR, "the reference tree") == tmp_path
