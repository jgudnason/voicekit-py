"""``GciResult.goi_candidates`` (GIF6): the GOI candidate set the closed-phase weighter consumes.

The *behaviour guard* for this additive field lives in ``test_yaga_detector`` --
its end-to-end tests read the committed golden ``.npz`` and assert ``gci``/``goi``
bit-exact and ``residual`` to epsilon on the 16 kHz fixtures (8 kHz is F1-sanity).
Those tests stay green after the field is added, which is the behaviour-preserving
proof: the field is threaded out of the ``setdiff`` the detector already ran, so it
cannot perturb ``gci``/``goi``/``residual``. This file pins the new field's *own*
semantics against the reference candidate capture.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.io import read_wav
from voicekit.yaga.detector import yaga

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"


@pytest.mark.parametrize("name", ["vowel_f0100_16k", "vowel_glide_16k"])
def test_goi_candidates_match_reference_capture_16k(name: str) -> None:
    """``goi_candidates`` equals the reference ``goic`` positions (0-based), content AND order.

    WHY content-and-order rather than set-equality: the reference builds
    ``goic = setdiff(gcic, gci)`` with MATLAB ``setdiff``, which DEDUPS and sorts;
    voicekit builds the same leftover set with ``~np.isin``, which does NOT dedup.
    On every committed fixture the candidate positions are unique, so the two agree
    exactly -- but that is COINCIDENCE (no zero-crossing/projected candidate lands
    on the same sample), not coupling: nothing structural forces them to keep
    agreeing. This exact-equality assertion is what would catch a divergence the
    day a duplicate candidate position arises; the field construction would then
    need to dedup to stay faithful to the reference.
    """
    d = np.load(GOLDEN / f"{name}.npz")
    gcis = yaga(read_wav(FIXTURES / f"{name}.wav")).gcis
    expected = d["ret_goic"][:, 0].astype(np.int64) - 1  # reference goic positions, 0-based
    np.testing.assert_array_equal(gcis.goi_candidates, expected)


def test_goi_candidates_shape_dtype_and_distinct_from_goi() -> None:
    """0-based sorted int64, and a structurally different object from ``goi``."""
    gcis = yaga(read_wav(FIXTURES / "vowel_f0100_16k.wav")).gcis
    gc = gcis.goi_candidates
    assert gc.dtype == np.int64
    assert np.all(np.diff(gc) >= 0)  # sorted ascending
    assert gc.min() >= 0  # 0-based, no -1 sentinel
    # ``goi`` is one entry per cycle (aligned to ``gci``); ``goi_candidates`` is the
    # raw candidate set -- different lengths, so a consumer cannot mistake one for
    # the other. (They also diverge in content; see GIF6 / the class docstring.)
    assert gc.size != gcis.goi.size


def test_goi_candidates_8k_is_live_not_the_capture() -> None:
    """8 kHz cannot match the reference capture (F1) -- but is still a sane set.

    Live IAIF differs from the 8 kHz capture's clean-residual injection, so the
    candidate set differs from the captured ``ret_goic`` exactly as ``gci``/``goi``/
    ``residual`` do. The field is still a 0-based sorted int64 set.
    """
    d = np.load(GOLDEN / "vowel_f0120_8k.npz")
    gc = yaga(read_wav(FIXTURES / "vowel_f0120_8k.wav")).gcis.goi_candidates
    expected = d["ret_goic"][:, 0].astype(np.int64) - 1
    assert not (gc.shape == expected.shape and np.array_equal(gc, expected))  # F1
    assert gc.dtype == np.int64
    assert np.all(np.diff(gc) >= 0)
    assert gc.min() >= 0
