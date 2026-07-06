"""Tests for the precomputable per-candidate DP cost terms.

Golden master (sole arbiter): each cost vector against its full-length (241)
capture on all three fixtures. Because these are floats, agreement is
machine-epsilon, not the bit-exact integer equality of pieces 2/3 (candidate
positions and flags are exact, the cost floats are not). Captured upstream
arrays (zcr_cand_raw, sew_raw, pro_cand, s_used, udash, fnwav, dp_gcic) are
fed as data -- each function is tested in isolation, not wired to the others.

Orthogonal checks (fixture- and library-independent): the trapezoidal energy
window from an impulse; the running-max pad exercised by a tail candidate
(the fixtures trim candidates short of the pad region, so only an orthogonal
case reaches it); the closed-phase interval mean hand-computed on a geometric
residual, which also smokes out the adjacency / inclusive-range convention.
There is no clean library cross-check for any of these DYPSA-specific costs.
"""

from pathlib import Path

import numpy as np
import pytest

from voicekit.yaga import dp_costs as dc

GOLDEN = Path(__file__).resolve().parent / "golden"
FIXTURES = ["vowel_f0100_16k", "vowel_glide_16k", "vowel_f0120_8k"]


# --- 1. Golden master (the arbiter) ----------------------------------------


@pytest.mark.parametrize("name", FIXTURES)
def test_candidate_assembly_matches_capture(name):
    """Assembled positions, flags and phase-slope cost reproduce dp_gcic/dp_sew."""
    d = np.load(GOLDEN / f"{name}.npz")
    # Captured candidate arrays are 1-based; feed them 0-based, as the live
    # piece-2/3 modules would produce.
    result = dc.assemble_candidates(
        zcr_positions=d["zcr_cand_raw"] - 1,
        zcr_slopes=d["sew_raw"],
        projected_positions=d["pro_cand"] - 1,
        gdwav_length=len(d["gdwav"]),
        fs=float(d["input_fs"]),
    )
    ref_pos = d["dp_gcic"][:, 0]
    ref_flag = d["dp_gcic"][:, 1]
    np.testing.assert_array_equal(result.positions + 1, ref_pos)  # 0-based -> 1-based
    np.testing.assert_array_equal(result.is_zero_crossing, ref_flag == 1)
    np.testing.assert_allclose(result.phase_slope_cost, d["dp_sew"], rtol=1e-12, atol=1e-12)
    # Projected penalty column (mycost col 3): 0.5 for projected, 0 for zcr.
    np.testing.assert_array_equal(result.projected_penalty, (1.0 - ref_flag) / 2.0)


@pytest.mark.parametrize("name", FIXTURES)
def test_frobenius_energy_function_matches_capture(name):
    """frobfun reproduces the captured fnwav."""
    d = np.load(GOLDEN / f"{name}.npz")
    fnwav = dc.frobenius_energy_function(d["s_used"], float(d["input_fs"]))
    assert fnwav.shape == d["fnwav"].shape
    np.testing.assert_allclose(fnwav, d["fnwav"], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_frobenius_energy_cost_matches_capture(name):
    """fnrg reproduces the captured per-candidate Frobenius cost."""
    d = np.load(GOLDEN / f"{name}.npz")
    positions = d["dp_gcic"][:, 0].astype(np.int64) - 1  # captured positions, 0-based
    cfn = dc.frobenius_energy_cost(positions, d["fnwav"], float(d["input_fs"]))
    np.testing.assert_allclose(cfn, d["vus_dp_Cfn"], rtol=1e-10, atol=1e-12)


@pytest.mark.parametrize("name", FIXTURES)
def test_closed_phase_cost_matches_capture(name):
    """The anticausal/causal closed-phase costs reproduce aencost/cencost."""
    d = np.load(GOLDEN / f"{name}.npz")
    positions = d["dp_gcic"][:, 0].astype(np.int64) - 1
    aencost, cencost = dc.closed_phase_cost(d["udash"], positions)
    np.testing.assert_allclose(aencost, d["aencost"], rtol=1e-10, atol=1e-12)
    np.testing.assert_allclose(cencost, d["cencost"], rtol=1e-10, atol=1e-12)


# --- 2. Orthogonal, hand-built checks --------------------------------------


def test_frobfun_impulse_is_the_trapezoidal_window():
    """An energy impulse reproduces the trapezoidal window at the aligned offset.

    frob = filter(w, delta) is w shifted to the impulse; after dropping the
    leading `drop` samples, the window appears at fnwav[q-drop:]. This pins the
    window shape (ramp/flat/ramp) and the alignment deletion, independently.
    """
    fs = 16000.0
    cfg = dc.FrobeniusConfig()
    p = int(round(cfg.ew_taper * fs))  # 16
    m = int(round(cfg.ew_len * fs))  # 48
    offset = int(round(cfg.ew_dly * fs))  # 13
    drop = int(round((p + m - 1) / 2)) + offset  # round(31.5) + 13 = 45

    w = np.full(m + p, p + 1, dtype=float)
    w[:p] = np.arange(1, p + 1)
    w[m : m + p] = np.arange(p, 0, -1)
    w = w / (p + 1)

    q = 200
    sp = np.zeros(400)
    sp[q] = 1.0
    fnwav = dc.frobenius_energy_function(sp, fs, cfg)
    np.testing.assert_allclose(fnwav[q - drop : q - drop + len(w)], w, atol=1e-12)


def test_frobenius_cost_constant_energy_is_minus_half():
    """Constant energy makes fnwav/runningmax == 1, so Cfn == 0.5 - 1 == -0.5."""
    fnwav = np.full(500, 3.7)
    cfn = dc.frobenius_energy_cost(np.array([50, 250, 480]), fnwav, 16000.0)
    np.testing.assert_allclose(cfn, -0.5, atol=1e-12)


def test_frobenius_cost_pad_and_shift_at_tail():
    """A tail candidate is normalized by the padded running max; an interior one by the shift.

    With mm = round(300/60) = 5 (half=2, ceil_half=3), mfrob is the trailing max
    shifted left by 2 and end-padded (last 2 entries) with max of the last 4
    samples. On fnwav = 1..20: interior index 10 -> runningmax(fnwav[8:13])=13;
    tail index 18 is in the pad region -> pad = max(fnwav[16:]) = 20.
    """
    fnwav = np.arange(1.0, 21.0)  # 1..20
    cfn = dc.frobenius_energy_cost(np.array([10, 18]), fnwav, fs=300.0)
    expected = np.array([0.5 - 11.0 / 13.0, 0.5 - 19.0 / 20.0])  # [interior, tail]
    np.testing.assert_allclose(cfn, expected, atol=1e-12)


def test_closed_phase_interval_mean_and_adjacency():
    """Closed-phase means over inclusive ranges, including an adjacent (1-sample) pair.

    The residual is a unit impulse, so the leaky integrator gives u[k] = 0.99**k.
    Positions [2, 2, 5]: the first interval is the single sample u[2] (adjacent
    candidates -> 1-sample mean, no empty-slice NaN); the second is the mean of
    u[2..5] inclusive; the last entry is a structural 0, which is included in
    the normalizing mean(|aencost|). Computed here from the closed form, so it
    is independent of the module's lfilter/slicing.
    """
    udash = np.zeros(10)
    udash[0] = 1.0
    u = 0.99 ** np.arange(10)  # closed form of the leaky integrator's impulse response

    a0 = u[2:3].mean()  # adjacent pair -> single sample
    a1 = u[2:6].mean()  # inclusive range 2..5
    raw = np.array([a0, a1, 0.0])  # trailing 0 is structural
    expected_ae = 0.5 * raw / np.mean(np.abs(raw))  # 0 included in the denominator
    expected_ce = np.concatenate([[0.0], expected_ae[:-1]])

    aencost, cencost = dc.closed_phase_cost(udash, np.array([2, 2, 5]))
    np.testing.assert_allclose(aencost, expected_ae, atol=1e-12)
    np.testing.assert_allclose(cencost, expected_ce, atol=1e-12)
