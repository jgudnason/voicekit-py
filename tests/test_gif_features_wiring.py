"""Features-wiring closure for the continuous-weight GIF methods (step 8 close).

Each method's feature path -- ``method_gif`` -> ``u``/``uu`` -> ``extract_voice_features``
-> ``apply_invalid_frame_mask`` -> `VoiceFeatures` -- is validated **transitively**,
the same composition argument step 6 used to close its orchestration seam
(``test_features_extract``, the "J4" join) without re-capturing a full-pipeline golden.
Three links, each already pinned:

  1. **Flow parity.** ame/rgauss/agauss ``u``/``uu`` match the reference end-to-end at
     machine-eps (``test_gif_ame`` / ``test_gif_rgauss`` / ``test_gif_agauss``,
     rtol=1e-6, observed abs deviation <= 1e-12).

  2. **Extractor.** ``extract_voice_features(u, uu, fs, gci, config)`` is validated on
     captured ``u``/``uu`` at machine-eps (step 6, ``test_features_extract``). Its
     signature takes ONLY method-independent inputs -- ``u``/``uu`` (parity-validated
     flow), ``fs``, the detection ``gci``, and a `FeaturesConfig` (NOT the method's
     config) -- so it structurally cannot distinguish which method produced the flow.
     Validating it on captured flow validates it on any parity-matched flow.

  3. **Mask.** ``apply_invalid_frame_mask(feats, gci, result)`` reads only the
     shared-core `WeightedLpResult` fields (``frame_valid``, ``frame_starts``,
     ``uu.size``), produced identically for all four methods, and is validated by
     glide/cp's live rank-deficient frame (``test_gif_feature_mask``, the forward-smear
     extent). It reads nothing method-specific.

Transitivity validates each link ASSUMING the pieces connect. What it does not cover is
that they actually connect -- no attribute/shape/type mismatch at the seam. That is the
one thing these smoke tests add: they drive the full path per method and assert a
well-formed `VoiceFeatures`. No numerical golden (that would re-validate the three links
in composition -- the redundancy step 6 declined). For these three methods
``frame_valid`` is all-true, so the mask is a no-op (``reason`` all ``"valid"``); the
``frame_valid`` False branch is glide/cp's, not re-proved here.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.features import apply_invalid_frame_mask, extract_voice_features
from voicekit.features.extract import _VOICING_MASK_SUBSET
from voicekit.gif.ame import ame_gif
from voicekit.gif.gaussian import agauss_gif, rgauss_gif

GOLDEN = Path(__file__).resolve().parent / "golden"
METHODS = {"ame": ame_gif, "rgauss": rgauss_gif, "agauss": agauss_gif}


@pytest.mark.parametrize("method", list(METHODS))
def test_features_wiring_composes(method: str) -> None:
    z = np.load(GOLDEN / "vowel_f0100_16k.npz")
    sp = np.asarray(z["input_s"], dtype=np.float64)
    fs = float(z["input_fs"])
    gci = np.asarray(z["gci"], dtype=np.int64) - 1  # 0-based; these methods read gci only

    # method -> flow -> features -> mask, end to end (the connection under test).
    result = METHODS[method](sp, fs, gci)
    assert np.all(np.isfinite(result.u)) and np.all(np.isfinite(result.uu))  # finite flow in

    feats = extract_voice_features(result.u, result.uu, fs, gci)
    masked, reason = apply_invalid_frame_mask(feats, gci, result)

    # well-formed: one row per cycle, aligned 1:1 with gci, across every masked field.
    assert reason.shape == (gci.size,)
    for name in _VOICING_MASK_SUBSET:
        assert getattr(masked, name).shape == (gci.size,)

    # these methods have no rank-deficient frame, so the mask is a no-op: reason is all
    # "valid" and it introduces no NaN -- masked equals the extractor output. NaN only
    # where the mask puts it (here, nowhere); the frame_valid=False branch is glide/cp's.
    assert set(np.unique(reason).tolist()) == {"valid"}
    assert result.frame_valid.all()
    for name in _VOICING_MASK_SUBSET:
        np.testing.assert_array_equal(getattr(masked, name), getattr(feats, name))
