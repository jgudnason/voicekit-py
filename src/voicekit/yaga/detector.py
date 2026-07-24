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
    TASLP 15(1), 34-43. Reference: the reference GCI/GOI detector, reimplemented from the
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

# GOI positions the reference's postGOI step emits when it cannot pair (see below).
_GOI_SENTINEL = -1.0


def _default_iaif_config() -> IaifConfig:
    # the reference detector calls IAIF as iaif(s, fs, 20, 4, 20, 1):
    # vocal-tract order 20, glottal 4.
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
    # GOI post-processing (the reference's postGOI GCI/GOI pairing). See
    # REFERENCE_NOTES entry 5. True reproduces the reference (including its bug) for
    # parity; False *skips* the buggy pairing (raw GOI-DP output) -- which is NOT the
    # fix, only its absence. The correct boundary-aware pairing is in neither branch.
    goi_postprocess: bool = True


@dataclass(frozen=True)
class GciResult:
    """Output of `yaga`.

    ``gci`` are 0-based sample positions of glottal closures. ``goi`` is a
    per-cycle-aligned companion: ``goi[i]`` is the 0-based glottal *opening*
    within the cycle that begins at ``gci[i]``, or ``NaN`` if no opening was
    detected for that cycle (unvoiced transitions, creak, or -- see
    REFERENCE_NOTES entry 5 -- a cycle the reference's buggy GOI pairing failed
    to fill). It is ``float`` so absence is ``NaN`` rather than a poison index;
    a consumer must check ``np.isnan(goi[i])`` before using it. ``candidates`` is
    the assembled, classified candidate set the DP chose from.

    ``goi`` and ``goi_candidates`` are two DIFFERENT objects and must not be
    collapsed. ``goi`` is the detector's per-cycle opening *estimate* -- what
    feature timing consumes -- from the DP/postGOI pairing, NaN-for-absent.
    ``goi_candidates`` is the raw set of GOI *candidate* positions (0-based,
    sorted int): the assembled candidates not DP-selected as GCIs. It is the
    input the closed-phase weighter reconstructs the reference's own gap-free
    GOI sequence from (a nearest-candidate-to-a-priori-point selection step, not
    the pairing ``goi`` records), so the closed-phase mask cannot be built from
    ``goi``. The two sequences genuinely diverge -- on 55/55 cycles (median 28
    samples) of the 16 kHz fixture -- so a consumer must not substitute one for
    the other. See REFERENCE_NOTES GIF6.
    """

    gci: npt.NDArray[np.int64]
    goi: npt.NDArray[np.float64]
    candidates: CandidateSet
    goi_candidates: npt.NDArray[np.int64]


@dataclass(frozen=True)
class YagaResult:
    """Output of `yaga`: the GCI/GOI detection plus the residual it ran on.

    ``gcis`` is the `GciResult` (closures, openings, candidates). ``residual`` is the
    IAIF glottal-flow derivative (``udash``) that the whole pipeline was computed
    from, returned so a downstream stage -- e.g. feature extraction deriving the flow
    ``u`` from ``udash`` -- can reuse the exact residual of this one IAIF run instead
    of re-running IAIF and having to re-select an `IaifConfig` (which could silently
    diverge; see the 10/4/10-vs-20/4/20 trap that made `IaifConfig` orders required).
    The residual is *returned, never accepted*: yaga owns the single IAIF config site,
    so a caller cannot inject a mismatched residual.
    """

    gcis: GciResult
    residual: npt.NDArray[np.float64]  # udash: IAIF flow derivative, length == len(signal)

    def __post_init__(self) -> None:
        # Lock the residual read-only. yaga *returns* it and never accepts one, so a
        # caller must not be able to forge it by in-place mutation -- frozen blocks
        # rebinding the field, not writing through the array. yaga's residual owns its
        # data (base is None), so clearing the writeable flag fully closes the door.
        self.residual.flags.writeable = False


def _goi_postprocess(
    gci: npt.NDArray[np.int64], goi_dp: npt.NDArray[np.int64]
) -> npt.NDArray[np.float64]:
    """Reference ``postGOI`` pairing: enforce GCI-GOI alternation. Reproduces its bug.

    Interleaves GCIs (+1) and GOIs (-1) by position; where two GCIs are adjacent it
    inserts an opening at ``gci + previous-opening-period``, and drops a stray
    opening where two are adjacent. When there is no previous opening (signal
    start) the insertion collapses to the reference's ``-1`` sentinel. See
    REFERENCE_NOTES entry 5 -- the count mismatch and the sentinels are the bug,
    reproduced for parity.
    """
    pos = np.concatenate([gci.astype(np.float64), goi_dp.astype(np.float64)])
    lab = np.concatenate([np.ones(gci.size), -np.ones(goi_dp.size)])
    order = np.argsort(pos, kind="stable")
    pos, lab = pos[order], lab[order]

    adj = lab.copy()
    adj[1:] = lab[1:] + lab[:-1]  # fftfilt([1 1], lab): two adjacent same-label markers
    add = np.where(adj > 0)[0]  # 1-based find(adj>0) - 1 == this 0-based index
    add[add == 0] = 1
    lab[np.where(adj < 0)[0]] = 0  # flag stray openings for removal

    added = []
    for pi in add:  # pi is a 1-based index into the interleaved arrays
        prev = np.where(lab[:pi] == -1)[0]  # closest previous opening, 0-based
        if prev.size == 0:
            added.append(_GOI_SENTINEL)  # no previous opening -> reference emits -1
        else:
            i1 = prev[-1] + 1  # 1-based index of that opening
            nb = i1 if i1 > 1 else i1 + 1  # neighbour to measure the period against
            added.append(pos[pi - 1] + (pos[nb - 1] - pos[nb - 2]))
    kept = pos[lab == -1]
    return np.sort(np.concatenate([kept, np.array(added, dtype=np.float64)]))


def _detect_goi_raw(
    positions_1based: npt.NDArray[np.int64],
    flags: npt.NDArray[np.int64],
    phase_slope: npt.NDArray[np.float64],
    cencost: npt.NDArray[np.float64],
    gci_dp: npt.NDArray[np.int64],
    gci_refined: npt.NDArray[np.int64],
    residual: npt.NDArray[np.float64],
    fnwav: npt.NDArray[np.float64],
    fs: float,
    config: "YagaConfig",
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64]]:
    """Raw GOI sequence plus the GOI candidate set it was selected from.

    GOI candidates are the assembled candidates *not* chosen as GCIs; the same DP
    forward pass and traceback run on them with the causal closed-phase cost
    ``cencost`` (where GCI used the anticausal ``aencost``). Then the ``postGOI``
    pairing runs, unless ``goi_postprocess`` is off.

    Returns ``(raw_goi, goi_candidates)``. ``goi_candidates`` is the leftover
    candidate set (0-based, sorted) -- the single ``setdiff`` computed here and
    exposed on `GciResult` so the closed-phase weighter consumes it rather than
    recomputing it (see REFERENCE_NOTES GIF6).
    """
    leftover = ~np.isin(positions_1based.astype(np.int64), np.asarray(gci_dp, np.int64))
    idx = np.nonzero(leftover)[0]
    goic = positions_1based[idx]  # 1-based candidate positions
    goi_candidates = (goic - 1).astype(np.int64)  # 0-based; the exposed setdiff
    frob_cost = frobenius_energy_cost(goic.astype(np.int64) - 1, fnwav, fs, config.frobenius)
    result = forward_pass(
        goic, flags[idx], residual, phase_slope[idx], frob_cost, cencost[idx], fs, config.dp
    )
    goi_dp = traceback(result, goic, fs, config.dp, config.traceback_force_penultimate)
    if config.goi_postprocess:
        raw_goi = _goi_postprocess(gci_refined, goi_dp)
    else:
        raw_goi = np.sort(goi_dp.astype(np.float64))
    return raw_goi, goi_candidates


def _align_goi_to_cycles(
    gci_1based: npt.NDArray[np.int64], raw_goi: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """Pair each GCI cycle with its opening; drop sentinels; return 0-based, NaN for absent.

    ``goi[i]`` is the opening within ``(gci[i], gci[i+1])`` (or after the last GCI
    for the final cycle), or NaN if none. Sentinels and any opening before the
    first GCI fall below ``gci[0]`` and are never assigned, so they drop out.
    """
    gci = np.sort(np.asarray(gci_1based, dtype=np.int64))
    raw = np.sort(np.asarray(raw_goi, dtype=np.float64))
    out = np.full(gci.size, np.nan)
    for i in range(gci.size):
        upper = gci[i + 1] if i + 1 < gci.size else np.inf
        in_cycle = raw[(raw > gci[i]) & (raw < upper)]
        if in_cycle.size:
            out[i] = in_cycle[0]  # at most one per cycle (verified on the fixtures)
    return out - 1  # 1-based positions -> 0-based; NaN stays NaN


def yaga(signal: Signal, config: YagaConfig | None = None) -> YagaResult:
    """Detect glottal closure instants in ``signal`` with the DYPSA-derived pipeline.

    Returns a `YagaResult`: the `GciResult` detection plus the IAIF ``residual`` the
    pipeline ran on, so callers reuse that one residual rather than re-running IAIF.
    """
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
    aencost, cencost = closed_phase_cost(udash, candidates.positions)  # anticausal / causal

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
    gci_dp = traceback(result, positions_1based, fs, cfg.dp, cfg.traceback_force_penultimate)
    gci = refine_gcis(gci_dp, crnmp, cfg.refine_tol, cfg.refine_min_sep)  # 1-based

    # GOI: the leftover candidates through the same DP with the causal closed-phase
    # cost, then the reference's pairing. The raw goi (with sentinels) is cleaned to
    # the per-cycle representation for the public result.
    raw_goi, goi_candidates = _detect_goi_raw(
        positions_1based,
        candidates.is_zero_crossing.astype(np.int64),
        candidates.phase_slope_cost,
        cencost,
        gci_dp,
        gci,
        udash,
        fnwav,
        fs,
        cfg,
    )
    goi = _align_goi_to_cycles(gci, raw_goi)
    gcis = GciResult(gci=gci - 1, goi=goi, candidates=candidates, goi_candidates=goi_candidates)
    return YagaResult(gcis=gcis, residual=udash)
