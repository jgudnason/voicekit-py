"""Assertions on the committed conditioning-hazard fixtures (H0-H4).

These assert the **structural claims** the fixture exists to pin -- that each
hazard reads false-voiced unconditioned and correctly non-voiced after
`condition()`, and that the check fires as ratified. The per-case predicted
values (written before the fixture was built) and their outcomes are recorded
in ``tests/synthetic/README.md``; the bands there are the derivation's record,
whereas the bounds asserted here are the claims a regression must not break.
Both matter and they are not the same thing: a band that a good derivation
misses is a finding, while these bounds failing means the detector's input
boundary has broken.

rho_env's declared range is 0.53-0.81 (docs/vuv_rho_env.md), so "reads voiced"
means > 0.81 (above the whole range, unambiguous) and "reads non-voiced" means
< 0.1 (far below the floor). Those two numbers are the range's, not fitted.
"""

import warnings

import pytest
from tests.synthetic.vuv_fixture import load_conditioning_cases

from voicekit.vuv import check_precondition, condition, r1
from voicekit.vuv.grid import VoicingGrid

RHO_ENV_MAX = 0.81  # top of the declared rho_env range: above it, unambiguously voiced
NON_VOICED_MAX = 0.1  # far below the range's 0.53 floor: unambiguously non-voiced


def _r1_mean(signal):
    grid = VoicingGrid()
    fl, hop = grid.frame_len(float(signal.fs)), grid.hop(float(signal.fs))
    s = signal.samples
    n = (len(s) - fl) // hop
    return sum(r1(s, k * hop, fl) for k in range(1, n + 1)) / n


def _cases():
    return {c.name: c for c in load_conditioning_cases()}


def test_all_five_cases_present_with_construction_labels():
    cases = _cases()
    assert set(cases) == {
        "vuv_h0_clean_16k",
        "vuv_h1_dc_16k",
        "vuv_h2_hum_16k",
        "vuv_h3_humvoiced_16k",
        "vuv_h4_lowf0_16k",
    }
    # The label rule settles the impostor by construction: hum is periodic but
    # is not phonation, so the hum-only case is non-voiced ground truth.
    assert cases["vuv_h2_hum_16k"].label == "N"
    assert cases["vuv_h3_humvoiced_16k"].label == "V"


@pytest.mark.parametrize("name", ["vuv_h1_dc_16k", "vuv_h2_hum_16k"])
def test_hazard_reads_false_voiced_unconditioned(name):
    # THE hazard, both flavours: a non-voiced signal reading as voiced. H2 is
    # the one that matters -- hum is genuinely periodic, so no threshold at any
    # alpha rejects it; only conditioning does (VUV12).
    case = _cases()[name]
    assert case.label == "N"
    assert _r1_mean(case.signal) > RHO_ENV_MAX


@pytest.mark.parametrize("name", ["vuv_h1_dc_16k", "vuv_h2_hum_16k"])
def test_conditioning_removes_the_hazard(name):
    case = _cases()[name]
    assert _r1_mean(condition(case.signal)) < NON_VOICED_MAX


def test_conditioning_preserves_the_voiced_verdict():
    # The control side: conditioning must not cost a voiced case its verdict,
    # including the hum-contaminated one (whose unconditioned r1 is right partly
    # for the wrong reason -- hum contributes to it).
    for name in ("vuv_h0_clean_16k", "vuv_h3_humvoiced_16k", "vuv_h4_lowf0_16k"):
        case = _cases()[name]
        assert case.label == "V"
        assert _r1_mean(condition(case.signal)) > RHO_ENV_MAX, name


def test_conditioning_barely_moves_clean_modal_voiced():
    # Predicted before building: drop < 0.01, because synth_vowel's energy sits
    # near F1 = 500 Hz where the filter is ~unity, so removing the (attenuated)
    # 120 Hz fundamental moves rho by ~0.002. Guards that claim.
    #
    # NOT generalizable to D3's breathy region, which is tilted low by
    # construction and may move more -- see docs/vuv_rho_env.md caveat (a),
    # which is a separate measurement with its own guard.
    case = _cases()["vuv_h0_clean_16k"]
    drop = _r1_mean(case.signal) - _r1_mean(condition(case.signal))
    assert 0.0 <= drop < 0.01


def test_check_raises_on_dc_and_only_warns_on_hum():
    # Enforcement tracks check confidence (VUV12 ruling): DC raises, hum warns.
    # The named cost is exactly this -- hum only warns.
    with pytest.raises(ValueError, match="DC offset"):
        check_precondition(_cases()["vuv_h1_dc_16k"].signal)

    with pytest.warns(UserWarning, match="below 70 Hz"):
        report = check_precondition(_cases()["vuv_h2_hum_16k"].signal)
    assert report.sub_band_violation
    assert not report.dc_violation  # hum is zero-mean: it must not trip the DC test


def test_check_is_silent_on_both_clean_voiced_cases():
    for name in ("vuv_h0_clean_16k", "vuv_h4_lowf0_16k"):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            report = check_precondition(_cases()[name].signal)
        assert not report.dc_violation, name
        assert not report.sub_band_violation, name


def test_low_f0_voice_is_nowhere_near_the_sub_band_edge():
    # H4, the boundary probe, and the finding it produced: an 85 Hz voice (a
    # realistic low-male floor) carries essentially NO energy below the 70 Hz
    # edge -- because a periodic signal's fundamental is its lowest component.
    # Hum at 50/60 Hz sits below the fundamental of any modal voice, not among
    # the harmonics of a low one. The margin is ~2 orders, not marginal: the
    # sub-band check is not near a false-positive boundary for modal speech.
    # Ledgered as VUV16.
    report = check_precondition(_cases()["vuv_h4_lowf0_16k"].signal, enforce=False)
    assert report.sub_band_energy_fraction < 0.01


def test_conditioning_clears_the_check_on_every_case():
    for case in load_conditioning_cases():
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            report = check_precondition(condition(case.signal))
        assert not report.dc_violation, case.name
        assert not report.sub_band_violation, case.name


def test_conditioning_barely_moves_the_d_series_r1():
    # Pins rho_env caveat (a)'s DISCHARGE (docs/vuv_rho_env.md): the D-fixtures'
    # r1 values were measured unconditioned while the margin they are checked
    # against derives from Table I's post-Eq.(1) chain, so the comparison is not
    # chain-matched. Measured 2026-07-17: every region moves by |delta| <= 0.014
    # -- an order below the 0.095 gap between D3's breathy (0.625) and the
    # range's 0.53 floor -- and breathy moves UP (+0.009), away from the floor.
    # Real in principle, negligible in practice.
    #
    # The bound is the caveat's claim, not a fitted constant: 0.02 is what
    # "negligible against a 0.095 gap" means. This test does NOT license moving
    # the range; the guard in the doc binds either way.
    from tests.synthetic.vuv_fixture import load_discriminating_fixture

    for name in ("vuv_d1_offset_16k", "vuv_d2_vfric_16k", "vuv_d3_breathy_16k"):
        fx = load_discriminating_fixture(name)
        conditioned = condition(fx.signal)
        for i, kind in enumerate(fx.region_kind):
            lo, hi = int(fx.region_start[i]), int(fx.region_end[i])
            before = _region_r1_mean(fx.signal, lo, hi)
            after = _region_r1_mean(conditioned, lo, hi)
            assert abs(after - before) < 0.02, f"{name}/{kind}: {after - before:+.4f}"


def _region_r1_mean(signal, lo: int, hi: int) -> float:
    grid = VoicingGrid()
    fl, hop = grid.frame_len(float(signal.fs)), grid.hop(float(signal.fs))
    starts = range(max(lo, 1), hi - fl + 1, hop)
    vals = [r1(signal.samples, st, fl) for st in starts]
    return sum(vals) / len(vals)
