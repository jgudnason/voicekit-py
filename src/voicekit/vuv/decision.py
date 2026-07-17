"""Decision-layer statistics for voicing detection.

This module is **define-the-target**, not capture-and-match: the reference's
decision stages were rejected at the architecture gate (non-deterministic GMM;
non-redistributable trained centroids), so there is no MATLAB oracle here and
**no parity claim attaches to anything in this module**. The feature layer
(`voicekit.vuv.features`) remains the golden-mastered reproduction of the
reference; this layer computes what the decision rule needs. Provenance and
rationale: ``docs/vuv_c1_decision.md`` (the decision record) and
``docs/vuv_r1_null.md`` (the null derivation behind any threshold).
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt


def r1(s: npt.NDArray[np.float64], start: int, frame_len: int) -> float:
    """Normalized autocorrelation coefficient at unit sample delay -- ``r1``.

    Atal & Rabiner (1976), Eq. (3), computed as published: for the frame
    ``x = s[start : start+frame_len]`` and its one-sample-delayed partner
    ``y = s[start-1 : start+frame_len-1]``,

        r1 = <x, y> / (||x|| * ||y||)

    The boundary sample ``s[start-1]`` enters the numerator **once** and the
    denominator once, so ``r1`` is an exact normalized inner product, bounded
    in [-1, +1] by Cauchy-Schwarz ("by definition, varies between -1 and +1",
    p. 204). This is deliberately **not** the feature layer's ``C1``, which
    reproduces the reference's broadcast of the boundary term (N-1 times,
    unbounded -- VUV7/VUV8); ``r1`` is a decision-layer statistic with **no
    parity claim** (see ``docs/vuv_c1_decision.md``).

    Null (docs/vuv_r1_null.md): white noise gives E[r1] = 0, std ~ 1/sqrt(N);
    coloured noise shifts the mean to ~ rho (the noise's own lag-1
    correlation) -- the coloured-noise floor is a bias, not estimation noise.

    A zero-energy frame yields 0/0 = ``NaN``; mapping that to a label is the
    decision rule's finiteness predicate (VUV1 J1), not the statistic's.
    ``start`` must be >= 1: the frame at 0 has no boundary sample, and
    refusing it here is what prevents a silent wrap to the signal tail.

    Reference: B. S. Atal and L. R. Rabiner, "A Pattern Recognition Approach
    to Voiced-Unvoiced-Silence Classification with Applications to Speech
    Recognition," IEEE Trans. ASSP-24(3), pp. 201-212, June 1976, Eq. (3).
    """
    if start < 1:
        raise ValueError(f"r1 needs the boundary sample s[start-1]; got start={start}")
    x = s[start : start + frame_len]
    y = s[start - 1 : start + frame_len - 1]
    with np.errstate(invalid="ignore"):
        return float((x @ y) / np.sqrt((x @ x) * (y @ y)))
