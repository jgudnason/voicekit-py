"""LF timing landmarks: closed-form values and the period identity."""

import pytest

from voicekit.lfmodel import lf_timing


def test_te_plus_tb_is_one_period() -> None:
    # The defining identity: the open-plus-return phase spans exactly 1/f0.
    for rk, rg, f0 in [(0.34, 1.17, 140.0), (0.2, 1.13, 300.0), (0.41, 0.88, 100.0)]:
        t = lf_timing(rk, rg, f0)
        assert t.te + t.tb == pytest.approx(1.0 / f0, rel=1e-12)


def test_tn_is_rk_times_tp() -> None:
    t = lf_timing(0.34, 1.17, 140.0)
    assert t.tn == pytest.approx(0.34 * t.tp, rel=1e-12)


def test_hand_computed_te_normal_140hz() -> None:
    # Rk=0.34, Rg=1.17, f0=140: Te = (1+Rk)/(2*Rg*f0).
    t = lf_timing(0.34, 1.17, 140.0)
    assert t.te == pytest.approx(1.34 / (2.0 * 1.17 * 140.0), rel=1e-12)
    assert t.tp == pytest.approx(0.5 / (1.17 * 140.0), rel=1e-12)


def test_rejects_nonpositive_f0_and_rg() -> None:
    with pytest.raises(ValueError, match="f0 must be positive"):
        lf_timing(0.34, 1.17, 0.0)
    with pytest.raises(ValueError, match="Rg must be positive"):
        lf_timing(0.34, 0.0, 140.0)
