"""Dynamic-program forward pass for YAGA GCI selection.

Given the assembled candidates and their costs, the DP finds the lowest-cost
sequence of glottal closures with an N-best (`dy_nbest = 5`) trellis over the
candidates. This module is the **forward pass** only: it populates the trellis
tables (`f_c` cumulative cost, `f_f` backpointer, `f_pq` previous period per
node, `f_fb` best end-of-spurt node) and the per-candidate waveform-window
statistics (`g_sqm`, `g_sd`). The traceback that reads these back into a GCI
sequence is a separate stage (sub-piece 3), and the reference's
penultimate-candidate traceback quirk lives there, not here.

The two path-dependent cost terms are the sub-piece-1 kernels, called per
transition (weighted by `dy_wxcorr`/`dy_wpitch`); the three precomputable
per-candidate costs (Frobenius energy, phase-slope, projected penalty) and the
closed-phase energy are combined with their weights into the per-candidate
fixed cost `g_cr`. The per-candidate `g_sqm`/`g_sd` are computed here (a small
stats helper) for the captured arbiter; a test cross-checks that they agree
with the kernel's internal statistics so the two computations cannot drift.

Talkspurt handling: a spurt start is marked by `f_pq == 0`, set either when the
best end-of-spurt node plus a projected penalty beats the worst N-best path, or
when a candidate has no feasible predecessor. `dy_cspurt` enters separately, as
a flat pitch cost on transitions *out of* a spurt-start node -- distinct from
the spurt-start transition cost `dy_cproj*(1-flag)`.

Note: the reference appends an artificial end state past the last candidate and
questions its own need for it ("why do we ever need the additional one at the
tail end?"). It is reproduced here; if it ever produces a spurious *final* GCI
(the mirror of the glide leading-GCI story), that source doubt is the place to
look.

References:
    P. A. Naylor, A. Kounoudes, J. Gudnason & M. Brookes (2007), DYPSA, IEEE
    TASLP 15(1), 34-43.

    Reference implementation: the ``dpgci`` forward loop of the VOICEBOX-bundled
    ``dypsagoi.m``. Reimplemented from the algorithm description, not ported.
"""

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from voicekit.yaga.dp_kernels import (
    PitchDeviationConfig,
    WaveformSimilarityConfig,
    pitch_deviation,
    waveform_similarity,
)

# Structural constants, hardcoded in the reference (not tunable parameters).
_START_STATE_GAP = 2  # extra samples beyond qrmax for the appended start/end states
_SPURT_QMIN_THRESHOLD = 2  # no spurt may start until qmin exceeds this (dypsa2 compat)


@dataclass(frozen=True)
class DpConfig:
    """Parameters of the DP forward pass.

    Composes the two sub-piece-1 kernel configs (so ``xwlen``/``spitch`` are not
    duplicated) and holds all eight cost-sum weights plus the search limits and
    N-best width. ``wamp`` and ``cspurt`` are hardcoded in the reference's
    ``dpgci`` rather than exposed as voicebox parameters, but a weight is a
    weight, so they live here with the rest for one cost-model source.
    """

    waveform: WaveformSimilarityConfig = field(default_factory=WaveformSimilarityConfig)
    pitch: PitchDeviationConfig = field(default_factory=PitchDeviationConfig)
    wener: float = 0.3  # Frobenius energy weight (dy_wener)
    wslope: float = 0.1  # phase-slope weight (dy_wslope)
    cproj: float = 0.2  # projected-candidate / spurt-start cost (dy_cproj)
    wxcorr: float = 0.8  # waveform-similarity weight (dy_wxcorr)
    wpitch: float = 0.5  # pitch-deviation weight (dy_wpitch)
    wamp: float = 0.5  # closed-phase energy weight (dy_wamp)
    cspurt: float = -0.45  # flat pitch cost out of a spurt start (dy_cspurt)
    fxmin: float = 50.0  # min larynx frequency -> max period (dy_fxmin)
    fxmax: float = 500.0  # max larynx frequency -> min period (dy_fxmax)
    nbest: int = 5  # number of paths kept per candidate (dy_nbest)


@dataclass(frozen=True)
class DpForwardResult:
    """Trellis tables from the forward pass, for the traceback (sub-piece 3).

    ``f_c``/``f_f``/``f_pq`` are per-node over the ``(Ncand+1)*nbest``-node
    trellis (node ``c*nbest + k`` is rank ``k`` of candidate slot ``c``, 0-based;
    candidate slot 0 is the appended start state). ``f_f`` holds 0-based node
    backpointers. ``f_fb`` is per candidate slot; ``g_sqm``/``g_sd`` per
    candidate.
    """

    f_c: npt.NDArray[np.float64]
    f_f: npt.NDArray[np.int64]
    f_pq: npt.NDArray[np.float64]
    f_fb: npt.NDArray[np.int64]
    g_sqm: npt.NDArray[np.float64]
    g_sd: npt.NDArray[np.float64]


def waveform_window_stats(
    residual: npt.NDArray[np.float64],
    positions: npt.NDArray[np.int64],
    fs: float,
    config: WaveformSimilarityConfig,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Per-candidate waveform-window statistics ``(sqrt(nx2)*mean, 1/(std*sqrt(nx2)))``.

    The same windowing as the waveform-similarity kernel (asymmetric window from
    ``ceil(xwlen*fs)``); reproduces the reference's ``g_sqm``/``g_sd``. Positions
    are 1-based.
    """
    residual = np.asarray(residual, dtype=np.float64)
    pos = np.atleast_1d(np.asarray(positions)).astype(np.int64)
    nxc = int(np.ceil(config.xwlen * fs))
    half = nxc // 2
    wavix = np.arange(-half, half + 2)  # asymmetric, matching the kernel
    nx2 = wavix.size
    win = residual[(pos[:, None] - 1) + wavix[None, :]]  # 1-based -> 0-based
    total = win.sum(axis=1)
    sqm = total / np.sqrt(nx2)
    sd = 1.0 / np.sqrt((win * win).sum(axis=1) - total**2 / nx2)
    return sqm, sd


def forward_pass(
    positions: npt.NDArray[np.int64],
    flags: npt.NDArray[np.int64],
    residual: npt.NDArray[np.float64],
    phase_slope_cost: npt.NDArray[np.float64],
    frobenius_cost: npt.NDArray[np.float64],
    closed_phase_cost: npt.NDArray[np.float64],
    fs: float,
    config: DpConfig | None = None,
) -> DpForwardResult:
    """Run the N-best DP forward pass over the assembled candidates.

    ``positions`` (1-based sample indices) and ``flags`` (1 = zero-crossing,
    0 = projected) are the assembled candidate set. ``phase_slope_cost`` (``Ch``),
    ``frobenius_cost`` (``Cfn``) and ``closed_phase_cost`` (``aencost``) are the
    unweighted per-candidate costs; ``residual`` is ``udash``. Returns the
    trellis tables; see `DpForwardResult`.
    """
    cfg = config if config is not None else DpConfig()
    nbest = cfg.nbest
    positions = np.asarray(positions, dtype=np.float64)
    ncand = positions.shape[0]
    qrmin = int(np.ceil(fs / cfg.fxmax))
    qrmax = int(np.floor(fs / cfg.fxmin))

    # Appended start/end states, and the padded per-candidate cost vectors.
    start = positions[0] - qrmax - _START_STATE_GAP
    end = positions[-1] + qrmax + _START_STATE_GAP
    g_n = np.concatenate([[start], positions, [end]])
    g_flag = np.concatenate([[0.0], np.asarray(flags, dtype=np.float64), [0.0]])
    cfn = np.concatenate([[0.0], np.asarray(frobenius_cost, dtype=np.float64), [0.0]])
    ch = np.concatenate([[0.0], np.asarray(phase_slope_cost, dtype=np.float64), [0.0]])
    enc = np.concatenate([[0.0], np.asarray(closed_phase_cost, dtype=np.float64), [0.0]])
    # Per-candidate fixed cost (weights enter here).
    g_cr = cfg.wener * cfn + cfg.wslope * ch + cfg.cproj * (1.0 - g_flag) + cfg.wamp * enc

    n_nodes = (ncand + 1) * nbest
    f_c = np.full(n_nodes, np.inf)
    f_c[0] = 0.0  # start node
    f_f = np.zeros(n_nodes, dtype=np.int64)  # 0-based node backpointers
    f_pq = np.zeros(n_nodes)
    f_fb = np.zeros(ncand + 1, dtype=np.int64)  # best end-of-spurt node per candidate
    fbestc = 0.0
    g_sqm = np.zeros(ncand + 1)
    g_sd = np.zeros(ncand + 1)

    qmin = 2  # 1-based candidate index; advances monotonically
    for r in range(2, ncand + 2):  # 1-based candidates 2..ncand+1
        c = r - 1  # 0-based candidate slot (also its node block)
        r_n = g_n[c]
        rix = c * nbest + np.arange(nbest)  # this candidate's nodes, best-first

        # Feasible previous candidates: period in [qrmin, qrmax]. qmin is the
        # first candidate no more than qrmax back; qmax the last at least qrmin
        # back. Both are 1-based candidate indices.
        qmin0 = qmin
        too_far = np.nonzero(g_n[qmin0 - 2 : r - 1] < r_n - qrmax)[0]
        qmin = (too_far[-1] + qmin0) if too_far.size else qmin0
        far_enough = np.nonzero(g_n[qmin - 2 : r - 1] <= r_n - qrmin)[0]
        qmax = (far_enough[-1] + qmin - 1) if far_enough.size else qmin - 1

        sqm_r, sd_r = waveform_window_stats(residual, np.array([r_n]), fs, cfg.waveform)
        g_sqm[c] = sqm_r[0]
        g_sd[c] = sd_r[0]

        if qmin <= qmax:
            qix = np.arange(qmin, qmax + 1)  # 1-based feasible q candidates
            q_pos = g_n[qix - 1]
            nq = qix.size

            # Waveform similarity (unweighted kernel) per feasible q, weighted.
            q_cas = cfg.wxcorr * waveform_similarity(
                residual, np.full(nq, r_n), q_pos, fs, cfg.waveform
            )

            # Node block for feasible q (candidate-major, rank-minor).
            fix = np.arange((qmin - 1) * nbest, qmax * nbest)
            period = np.repeat(r_n - q_pos, nbest)  # current period per node
            prev_period = f_pq[fix]  # previous period stored at each q-node

            # Pitch deviation (unweighted kernel), weighted; spurt-start override.
            f_cp = cfg.wpitch * pitch_deviation(period, prev_period, cfg.pitch)
            f_cp[prev_period == 0] = cfg.cspurt * cfg.wpitch

            transition = f_c[fix] + f_cp + np.repeat(q_cas, nbest)
            order = np.argsort(transition, kind="stable")
            best = order[:nbest]
            f_c[rix] = transition[best] + g_cr[c]
            f_f[rix] = fix[best]
            f_pq[rix] = period[best]

            # Start-of-spurt option: replace the worst N-best node if beginning a
            # new spurt from the best end-of-spurt node is cheaper.
            worst = rix[-1]
            if qmin > _SPURT_QMIN_THRESHOLD:
                start_node = f_fb[qmin - 2]  # f_fb(qmin-1), candidate qmin-1
                spurt_cost = f_c[start_node] + cfg.cproj * (1.0 - g_flag[c])
                if spurt_cost < f_c[worst]:
                    f_f[worst] = start_node
                    f_c[worst] = spurt_cost
                    f_pq[worst] = 0.0  # marks a spurt start

            if f_c[rix[0]] < fbestc:
                f_fb[c] = rix[0]
                fbestc = f_c[rix[0]]
            else:
                f_fb[c] = f_fb[c - 1]
        else:
            # No feasible predecessor: start a new spurt if past the threshold.
            if qmin > _SPURT_QMIN_THRESHOLD:
                start_node = f_fb[qmin - 2]
                f_c[rix[0]] = f_c[start_node] + cfg.cproj * (1.0 - g_flag[c])
                f_f[rix] = start_node
                f_pq[rix] = 0.0
            f_fb[c] = f_fb[c - 1]  # cannot be an end of spurt

    return DpForwardResult(f_c=f_c, f_f=f_f, f_pq=f_pq, f_fb=f_fb, g_sqm=g_sqm, g_sd=g_sd)
