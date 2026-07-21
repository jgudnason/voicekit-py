"""GOI-selection reconstruction (GIF6): consume goi_candidates, rebuild the gap-free GOI.

Synthetic hand-checks of the selection step's decomposition -- the nearest-pick,
the a-priori ``coc`` fallback, and the ceil-not-round convention -- not just a
final value. The behaviour is also validated against the reference ``pickGOIs``
via MATLAB in the capture path; these are the CI-safe pins.
"""

import numpy as np

from voicekit.gif.goi_selection import reconstruct_gois

APOP = 0.3  # voicebox('dy_cpfrac'), the source value


def test_nearest_candidate_to_coc_is_picked() -> None:
    # cycle 0: gci=100, dgci=100 -> coc = 100 + ceil(0.3*100) = 130. Candidates
    # 130 and 145 both lie strictly inside (100, 200); 130 is nearest to coc.
    gci = np.array([100, 200, 350], dtype=np.int64)
    cand = np.array([130, 145], dtype=np.int64)
    goi = reconstruct_gois(gci, cand, APOP)
    assert goi[0] == 130


def test_apriori_fallback_when_no_candidate_in_cycle() -> None:
    # cycle 1: gci=200, dgci=150 -> coc = 200 + ceil(0.3*150) = 245. No candidate
    # inside (200, 350), so the a-priori point is used -- never absent.
    gci = np.array([100, 200, 350], dtype=np.int64)
    cand = np.array([130], dtype=np.int64)  # only serves cycle 0
    goi = reconstruct_gois(gci, cand, APOP)
    assert goi[1] == 245


def test_uses_ceil_not_round() -> None:
    # dgci = 104 -> 0.3*104 = 31.2. ceil = 32 (reference), round = 31. With no
    # candidate the opening is exactly coc, so this isolates the rounding: the
    # result must be gci + 32, not gci + 31. (VUV9's round-vs-ceil class.)
    gci = np.array([0, 104], dtype=np.int64)  # dgci[0] = 104
    goi = reconstruct_gois(gci, np.empty(0, dtype=np.int64), APOP)
    assert goi[0] == 0 + int(np.ceil(0.3 * 104))  # 32
    assert goi[0] != 0 + round(0.3 * 104)  # 31 -- the wrong (round) answer


def test_candidates_strictly_inside_the_cycle() -> None:
    # Candidates exactly at gci or at gci+dgci are excluded (both bounds strict);
    # only the interior one is eligible, so it is picked despite being far from coc.
    gci = np.array([100, 200], dtype=np.int64)  # cycle 0 spans (100, 200)
    cand = np.array([100, 150, 200], dtype=np.int64)  # 100 and 200 on the bounds
    goi = reconstruct_gois(gci, cand, APOP)
    assert goi[0] == 150


def test_last_cycle_uses_zero_order_dgci() -> None:
    # The final open-ended cycle repeats the previous interval (MATLAB
    # dgci(end+1)=dgci(end)): here dgci[-1] = 100, so cycle 1's coc = 200 + 30.
    gci = np.array([100, 200], dtype=np.int64)
    goi = reconstruct_gois(gci, np.empty(0, dtype=np.int64), APOP)
    assert goi[1] == 200 + int(np.ceil(0.3 * 100))  # 230


def test_output_is_total_one_per_gci() -> None:
    gci = np.array([10, 40, 80, 130], dtype=np.int64)
    goi = reconstruct_gois(gci, np.array([25, 55], dtype=np.int64), APOP)
    assert goi.shape == gci.shape
    assert goi.dtype == np.int64  # no NaN -- a gap-free integer sequence
