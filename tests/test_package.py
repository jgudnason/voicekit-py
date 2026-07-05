"""Smoke tests: the package and all subpackages import cleanly."""

import importlib

import pytest

import voicekit

SUBPACKAGES = [
    "io",
    "lpc",
    "iaif",
    "yaga",
    "features",
    "vuv",
    "gif",
    "lfmodel",
    "pitch",
    "eval",
]


def test_version() -> None:
    assert voicekit.__version__


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    importlib.import_module(f"voicekit.{name}")
