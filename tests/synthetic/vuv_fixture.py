"""Loader for the synthetic V/UV/S ground-truth fixture (step 7).

Returns the raw signal and both ground-truth channels as committed. It performs
**no reduction** --- no frame-center lookup, no per-cycle assignment, no
label-to-framing collapse. Those belong to the (not-yet-designed) scorer, and
the framing decision (frame-based vs per-cycle) is deferred to the next gate;
providing a reduction helper here would silently make that choice. The loader
hands back the primary region table and the secondary voiced-only GCI list
side by side and stops.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from voicekit.io import read_wav
from voicekit.signal import Signal

FIXTURE_DIR = Path(__file__).resolve().parent
DEFAULT_NAME = "vuv_svuvs_16k"


@dataclass(frozen=True)
class VuvFixture:
    """A synthetic V/UV/S fixture: signal plus its two ground-truth channels.

    ``region_*`` is the PRIMARY oracle: a sample-accurate table covering all of
    S/U/V (start-inclusive, end-exclusive), including regions with no cycles.
    ``gci`` is the SECONDARY channel: true glottal-closure positions, voiced
    regions only, meaningful to a per-cycle path but structurally blind to S/U.
    """

    name: str
    signal: Signal
    region_start: npt.NDArray[np.int64]
    region_end: npt.NDArray[np.int64]
    region_class: npt.NDArray[np.str_]
    gci: npt.NDArray[np.int64]

    @property
    def fs(self) -> int:
        return self.signal.fs


def load_vuv_fixture(name: str = DEFAULT_NAME, directory: Path = FIXTURE_DIR) -> VuvFixture:
    """Load the committed signal (``.wav``) and labels (``.labels.npz``)."""
    signal = read_wav(directory / f"{name}.wav")
    labels = np.load(directory / f"{name}.labels.npz")
    return VuvFixture(
        name=name,
        signal=signal,
        region_start=labels["region_start"].astype(np.int64),
        region_end=labels["region_end"].astype(np.int64),
        region_class=labels["region_class"].astype(np.str_),
        gci=labels["gci"].astype(np.int64),
    )


@dataclass(frozen=True)
class DiscriminatingFixture:
    """A hard-case D-fixture: binary V/N ground truth plus construction metadata.

    ``region_label`` is the binary ground truth (``'V'``/``'N'``); ``region_kind``
    is the descriptive construction tag; ``region_hard_param`` is the per-region
    hard-regime metadata (SNR/VFR/HNR dB, named by ``hard_param_name``) — a
    stratification channel, not a label. ``gci_construction`` is the source
    closures known by construction (secondary; D1's mask-exercise test asserts
    against *detected* GCIs, not this list). Like the floor loader, this exposes
    the arrays raw and performs no lookup/reduction — a sample→region lookup is a
    ground-truth read the *consumer* does, not a helper baked in here.
    """

    name: str
    signal: Signal
    region_start: npt.NDArray[np.int64]
    region_end: npt.NDArray[np.int64]
    region_label: npt.NDArray[np.str_]
    region_kind: npt.NDArray[np.str_]
    region_hard_param: npt.NDArray[np.float64]
    hard_param_name: str
    gci_construction: npt.NDArray[np.int64]

    @property
    def fs(self) -> int:
        return self.signal.fs


def load_discriminating_fixture(name: str, directory: Path = FIXTURE_DIR) -> DiscriminatingFixture:
    """Load a committed discriminating fixture (``.wav`` + ``.labels.npz``)."""
    signal = read_wav(directory / f"{name}.wav")
    labels = np.load(directory / f"{name}.labels.npz")
    return DiscriminatingFixture(
        name=name,
        signal=signal,
        region_start=labels["region_start"].astype(np.int64),
        region_end=labels["region_end"].astype(np.int64),
        region_label=labels["region_label"].astype(np.str_),
        region_kind=labels["region_kind"].astype(np.str_),
        region_hard_param=labels["region_hard_param"].astype(np.float64),
        hard_param_name=str(labels["hard_param_name"]),
        gci_construction=labels["gci_construction"].astype(np.int64),
    )
