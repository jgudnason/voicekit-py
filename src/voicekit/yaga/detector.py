"""YAGA glottal-closure-instant detector -- the end-to-end pipeline.

`yaga` wires the five sub-pieces together on a raw speech signal: IAIF residual,
stationary wavelet multiscale product, energy-weighted group delay, phase-slope
projection, candidate assembly, per-candidate costs, the N-best dynamic program,
and finally traceback + peak-refinement. Every stage was validated in isolation
on captured inputs; this is the one place the live modules are composed, so it
is also the only place the frame hand-offs (1-based sample positions where the
DP's window extraction needs them, 0-based elsewhere) are exercised -- each is
called out explicitly below.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), DYPSA, IEEE
    TASLP 15(1), 34-43. Reference: ``dypsagoi.m``, reimplemented from the
    algorithm description.
"""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit.iaif import IaifConfig, iaif
from voicekit.signal import Signal
from voicekit.yaga.dp_costs import (
    CandidateSet,
    FrobeniusConfig,
    assemble_candidates,
    closed_phase_cost,
    frobenius_energy_cost,
    frobenius_energy_function,
)
from voicekit.yaga.dp_forward import DpConfig, forward_pass
from voicekit.yaga.dp_traceback import refine_gcis, traceback
from voicekit.yaga.group_delay import GroupDelayConfig, energy_weighted_group_delay
from voicekit.yaga.phase_slope import phase_slope_projection
from voicekit.yaga.swt import multiscale_product, negative_cube_root


def _default_iaif_config() -> IaifConfig:
    # dypsagoi calls iaif(s, fs, 20, 4, 20, 1): vocal-tract order 20, glottal 4.
    return IaifConfig(vt_order1=20, glottal_order=4, vt_order2=20)


@dataclass(frozen=True)
class YagaConfig:
    """Configuration for the full YAGA detector, composing the stage configs."""

    iaif: IaifConfig = field(default_factory=_default_iaif_config)
    group_delay: GroupDelayConfig = field(default_factory=GroupDelayConfig)
    frobenius: FrobeniusConfig = field(default_factory=FrobeniusConfig)
    dp: DpConfig = field(default_factory=DpConfig)
    swt_levels: int = 3
    preemph: float = 50.0  # pre-emphasis frequency (Hz) for the energy signal (dy_preemph)
    refine_tol: int = 10  # peak-refinement snap tolerance (samples)
    refine_min_sep: int = 50  # peak-refinement minimum peak separation (samples)
    # Bug-compatibility switch for the traceback: see dp_traceback.traceback and
    # REFERENCE_NOTES entry 3. True reproduces the reference bug for parity.
    traceback_force_penultimate: bool = True


@dataclass(frozen=True)
class GciResult:
    """Output of `yaga`.

    ``gci`` are 0-based sample positions of glottal closures. ``goi`` is None
    (GOI detection is deferred; this pipeline is GCI-first). ``candidates`` is
    the assembled, classified candidate set (positions and zero-crossing /
    projected flags) the DP chose from.
    """

    gci: npt.NDArray[np.int64]
    goi: npt.NDArray[np.int64] | None
    candidates: CandidateSet


def yaga(signal: Signal, config: YagaConfig | None = None) -> GciResult:
    """Detect glottal closure instants in ``signal`` with the DYPSA-derived pipeline."""
    cfg = config if config is not None else YagaConfig()
    fs = float(signal.fs)
    s = np.asarray(signal.samples, dtype=np.float64)

    # IAIF glottal-flow-derivative residual, and the pre-emphasized energy signal.
    udash = iaif(signal, cfg.iaif).glottal_flow_derivative
    s_used = scipy.signal.lfilter([1.0, -np.exp(-2 * np.pi * cfg.preemph / fs)], [1.0], s)

    # SWT multiscale product, then the GCI-branch cube-root of its negative half.
    crnmp = negative_cube_root(multiscale_product(udash, cfg.swt_levels))

    # Energy-weighted group delay + zero-crossing candidates, and projected ones.
    gd = energy_weighted_group_delay(crnmp, fs, cfg.group_delay)
    projected = phase_slope_projection(gd.group_delay)

    # Assemble the classified candidate set (0-based positions).
    candidates = assemble_candidates(
        gd.candidates, gd.slopes, projected, gd.group_delay.shape[0], fs
    )

    # Per-candidate costs. fnrg/closed-phase index signals with the 0-based
    # candidate positions directly.
    fnwav = frobenius_energy_function(s_used, fs, cfg.frobenius)
    frob_cost = frobenius_energy_cost(candidates.positions, fnwav, fs, cfg.frobenius)
    aencost, _cencost = closed_phase_cost(udash, candidates.positions)

    # The DP forward pass and traceback extract windows as residual[(pos-1)+...],
    # i.e. they need 1-based positions -- so shift the 0-based candidate positions
    # by +1 for these two stages only.
    positions_1based = candidates.positions + 1
    result = forward_pass(
        positions_1based,
        candidates.is_zero_crossing.astype(np.int64),
        udash,
        candidates.phase_slope_cost,
        frob_cost,
        aencost,
        fs,
        cfg.dp,
    )
    gci_dp = traceback(
        result, positions_1based, fs, cfg.dp, cfg.traceback_force_penultimate
    )

    # Peak-refinement works in the same 1-based frame; return 0-based GCIs.
    gci = refine_gcis(gci_dp, crnmp, cfg.refine_tol, cfg.refine_min_sep)
    return GciResult(gci=gci - 1, goi=None, candidates=candidates)
