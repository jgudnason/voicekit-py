"""Unit tests for the VoicingGrid frame substrate.

Grid arithmetic only -- no detector, no thresholds, no track. The load-bearing
test is ``test_voicing_grid_is_independent_of_iaif_framing``: VoicingGrid and
IaifConfig share a 32 ms frame length by coincidence, and a "DRY the two 32ms
constants" refactor must FAIL here rather than silently couple the voicing grid
to inverse-filtering framing.
"""

import inspect

import numpy as np

from voicekit.vuv import grid as grid_mod
from voicekit.vuv.grid import VoicingGrid


def test_grid_samples_at_16k():
    g = VoicingGrid()
    assert g.frame_len(16000) == 512
    assert g.hop(16000) == 160
    assert g.guard_band_samples(16000) == 336  # W = 512/2 + 160/2


def test_grid_samples_at_8k():
    g = VoicingGrid()
    assert g.frame_len(8000) == 256
    assert g.hop(8000) == 80
    assert g.guard_band_samples(8000) == 168  # W = 256/2 + 80/2


def test_frame_centers_and_nearest_center_projection_round_trip():
    g = VoicingGrid()
    centers = g.frame_centers(1000, 16000)  # 4 full frames at 16k
    np.testing.assert_array_equal(centers, [255.5, 415.5, 575.5, 735.5])
    for k, c in enumerate(centers):
        assert g.project(int(round(float(c))), 16000) == k


def test_projection_nearest_center_known_samples():
    g = VoicingGrid()
    assert g.project(255, 16000) == 0  # near frame-0 centre 255.5
    assert g.project(416, 16000) == 1  # near frame-1 centre 415.5
    assert g.project(736, 16000) == 3  # near frame-3 centre 735.5


def test_voicing_grid_is_independent_of_iaif_framing():
    """Coincidence guard: VoicingGrid and IaifConfig happen to share a 32 ms frame,
    but VoicingGrid defines its own durations and must be free to diverge. This guard
    is purely STRUCTURAL -- separately defined, not coupled -- and deliberately makes
    NO comparison of the two configs' values: not equality (which would pin them),
    not inequality (which would forbid their legitimate current agreement).

    The invariant is "own literals, no IAIF reference." A DRY refactor that sources
    0.032 from IaifConfig (or a shared module constant) trips one of these: the
    literal leaves VoicingGrid's class body, or an IAIF reference/import enters it.
    """
    src = inspect.getsource(VoicingGrid)
    assert "0.032" in src and "0.010" in src  # own literals, in its own class body
    assert "IaifConfig" not in src and "lpc_dur" not in src  # not referenced from IAIF
    assert not hasattr(grid_mod, "IaifConfig")  # grid module does not import IaifConfig
