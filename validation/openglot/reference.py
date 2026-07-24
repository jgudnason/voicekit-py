"""OpenGlot **R1** GCI reference construction and LF-pulse reconstruction.

R1 is LF-generated sustained vowels shipping a speech-pressure and a glottal-flow
channel, no annotations. The scored GCI reference is the closed form ratified in
REFERENCE_NOTES OG-GCI-A::

    n_k = k * ceil((N1 + N2) * fs / 48000) + (N1 - 1) * fs / 48000

with ``N1 = floor(48000 * Te)``, ``N2 = floor(48000 * Tb + 1)`` -- the generator
builds one pulse on a 48 kHz grid and resamples it to ``fs`` per pulse, so the
period is **not** ``fs/f0`` and ``t_e`` sits at 48 kHz grid index ``N1 - 1``. The
first pulse is dropped by ``synthFrame``, so sample 0 of every file is a pulse
start -- the train's phase is exact, not estimated.

Two functions here, different jobs:

- `reference_gci_train` -- the scored reference. Needs only LF *timing*
  (`voicekit.lfmodel.lf_timing`); no pulse synthesis. Returns **float** instants,
  un-rounded: ``(N1-1)*fs/48000`` is generally fractional (e.g. 32.5 for
  ``normal`` at 140 Hz), and rounding it would inject up to half a sample into the
  reference itself. How these float instants meet the integer-typed
  `score_gci_goi` is a **deferred** integration question, settled when the driver
  wires them together, not decided here.

- `reconstruct_lf_pulse` -- a faithful reconstruction of the shipped pulse
  (OpenGlot's ``lf.m``/``synthFrame.m`` generator), used to validate the closed
  form non-circularly: the analytic claim that ``t_e`` is the global ``-dU/dt``
  peak (A'-2) and, on the corpus, that the reconstruction reproduces the shipped
  waveform (P1). Reimplemented from OpenGlot's published generator, not ported.

This module is **R1-specific**. R2 (RepositoryII) is a different, kinematic
vocal-fold synthesis with a real closed phase and no analytic ``t_e``; its
reference is the ``-dUg/dt``-peak *operator* on the flow channel (OG-GCI), built
elsewhere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.signal import resample_poly

from voicekit.lfmodel import lf_timing

# The 48 kHz internal grid the generator synthesises every pulse on before
# resampling to the file's fs (OpenGlot ``lf.m``: ``fsH = 48000``).
FSH = 48000.0

# R1's file sampling rate (RepositoryI ships 8 kHz). A parameter, not a hardcode:
# the period/phase arithmetic is a formula in fs, so it is passed explicitly.
R1_FS = 8000.0

# Amplitude gain the generator applies to Ee before synthesis (``synthFrame.m``:
# ``gain = 0.1``). Irrelevant to the GCI train (timing only), load-bearing for the
# reconstruction's amplitude checks.
SYNTH_GAIN = 0.1

# Phonation-mode LF parameters (Ee, Ra, Rg, Rk), verbatim from OpenGlot's
# ``synthFrame.m``. Keys are RepositoryI's filename tokens. Ra/Ee matter only to
# the reconstruction; the GCI train depends on Rk, Rg alone.
MODE_PARAMS: dict[str, tuple[float, float, float, float]] = {
    "normal": (1.0, 0.01, 1.17, 0.34),  # 'Modal' in synthFrame.m
    "breathy": (10.0 ** (0.7 / 20.0), 0.025, 0.88, 0.41),
    "whispery": (10.0 ** (-4.6 / 20.0), 0.07, 0.94, 0.32),
    "creaky": (10.0 ** (-1.8 / 20.0), 0.008, 1.13, 0.2),
}


def _pulse_sample_counts(rk: float, rg: float, f0: float) -> tuple[int, int]:
    """The generator's 48 kHz open/return sample counts ``(N1, N2)``.

    ``N1 = floor(48000*Te)``, ``N2 = floor(48000*Tb + 1)`` (OpenGlot ``lf.m``).
    """
    t = lf_timing(rk, rg, f0)
    n1 = math.floor(FSH * t.te)
    n2 = math.floor(FSH * t.tb + 1)
    return n1, n2


def pulse_period(mode: str, f0: float, fs: float = R1_FS) -> int:
    """Inter-GCI period in output samples: ``ceil((N1+N2) * fs / 48000)``.

    This is the length the single 48 kHz pulse resamples to (the concatenation
    unit), **not** ``fs/f0`` -- see OG-GCI-A.
    """
    if mode not in MODE_PARAMS:
        raise ValueError(f"unknown phonation mode {mode!r}; known: {sorted(MODE_PARAMS)}")
    _, _, rg, rk = MODE_PARAMS[mode]
    n1, n2 = _pulse_sample_counts(rk, rg, f0)
    return math.ceil((n1 + n2) * fs / FSH)


def reference_gci_train(
    mode: str, f0: float, n_samples: int, fs: float = R1_FS
) -> npt.NDArray[np.float64]:
    """R1 reference GCI instants (float samples) over ``[0, n_samples)``.

    ``n_k = k*period + phase`` with ``period = ceil((N1+N2)*fs/48000)`` and
    ``phase = (N1-1)*fs/48000`` (the closure of the dropped-first-pulse train;
    OG-GCI-A). Float and un-rounded by decision -- the phase is generally
    fractional and rounding would corrupt the reference; see the module docstring.
    """
    if mode not in MODE_PARAMS:
        raise ValueError(f"unknown phonation mode {mode!r}; known: {sorted(MODE_PARAMS)}")
    if n_samples <= 0:
        raise ValueError(f"n_samples must be positive, got {n_samples}")
    _, _, rg, rk = MODE_PARAMS[mode]
    n1, n2 = _pulse_sample_counts(rk, rg, f0)
    period = math.ceil((n1 + n2) * fs / FSH)
    phase = (n1 - 1) * fs / FSH
    n_pulses = math.ceil((n_samples - phase) / period)
    if n_pulses <= 0:
        return np.empty(0, dtype=np.float64)
    return phase + period * np.arange(n_pulses, dtype=np.float64)


@dataclass(frozen=True)
class LfPulse:
    """A reconstructed single LF pulse, at 48 kHz and resampled to ``fs``.

    ``deriv48`` is the ``-dU/dt`` (flow-derivative) pulse at 48 kHz, length
    ``N1 + N2``; ``flow48`` its integral. ``deriv``/``flow`` are those resampled to
    ``fs``. ``ee_gain`` is the amplitude the pulse was built with (``0.1 * Ee``),
    the value ``deriv48`` reaches at ``t_e``.
    """

    n1: int
    n2: int
    te: float
    ee_gain: float
    deriv48: npt.NDArray[np.float64]
    flow48: npt.NDArray[np.float64]
    deriv: npt.NDArray[np.float64]
    flow: npt.NDArray[np.float64]


def reconstruct_lf_pulse(mode: str, f0: float, fs: float = R1_FS) -> LfPulse:
    """Reconstruct one shipped LF pulse (OpenGlot ``lf.m``), 48 kHz + resampled.

    Faithful reimplementation of the generator: the epsilon fixed-point, the
    ``E0``/``alpha`` amplitude solve, the two-segment open/return synthesis, and
    the per-pulse ``resample`` to ``fs``. Used to validate the closed form, not to
    build it. Reimplemented from OpenGlot's published generator, not ported.
    """
    if mode not in MODE_PARAMS:
        raise ValueError(f"unknown phonation mode {mode!r}; known: {sorted(MODE_PARAMS)}")
    ee, ra, rg, rk = MODE_PARAMS[mode]
    ee_gain = SYNTH_GAIN * ee
    t = lf_timing(rk, rg, f0)
    te, tb = t.te, t.tb
    wg = 2.0 * math.pi * rg * f0
    ta = ra / f0

    # epsilon fixed point: epsilon * Ta = 1 - exp(-epsilon * Tb).
    eps, delta = 1.0, 1.0
    while delta > 0.01:
        nxt = (1.0 - math.exp(-eps * tb)) / ta
        delta = abs(nxt - eps) / eps
        eps = nxt

    # E0/alpha solve so the two segments meet with matched area (lf.m's A -> 0 loop).
    a2 = -ee_gain / (eps**2 * ta) * (1.0 - math.exp(-eps * tb) * (1.0 + eps * tb))
    step, limit, e0 = 0.1, ee_gain / 100000.0, 1.0

    def _residual(e0_val: float) -> tuple[float, float]:
        alpha_val = 1.0 / te * math.log(-ee_gain / (e0_val * math.sin(wg * te)))
        a1 = e0_val * math.exp(alpha_val * te) / math.sqrt(alpha_val**2 + wg**2) * math.sin(
            wg * te - math.atan(wg / alpha_val)
        ) + e0_val * wg / (wg**2 + alpha_val**2)
        return a1 + a2, alpha_val

    residual, alpha = _residual(e0)
    while abs(residual) > limit:
        e0 = e0 - step if residual > 0 else e0 + step
        new_residual, alpha = _residual(e0)
        if np.sign(residual) != np.sign(new_residual):
            step /= 2.0
        residual = new_residual

    n1, n2 = _pulse_sample_counts(rk, rg, f0)
    t1 = np.linspace(0.0, te, n1)
    t2 = np.linspace(te, te + tb, n2 + 1)[1:]

    # Open phase (derivative u1, flow U1) and return phase (u2, U2), from lf.m.
    u1 = e0 * np.exp(alpha * t1) * np.sin(wg * t1)
    u2 = -ee_gain / (eps * ta) * (np.exp(-eps * (t2 - te)) - math.exp(-eps * tb))
    big_u1 = e0 * np.exp(alpha * t1) * np.sin(wg * t1 - math.atan(wg / alpha)) / math.sqrt(
        alpha**2 + wg**2
    ) + e0 * wg / (alpha**2 + wg**2)
    big_u2 = (
        ee_gain
        / (eps**2 * ta)
        * (np.exp(-eps * (t2 - te)) + eps * math.exp(-eps * tb) * (t2 - (1.0 / f0 + 1.0 / eps)))
    )
    deriv48 = np.concatenate([u1, u2])
    flow48 = np.concatenate([big_u1, big_u2])

    up, down = int(fs), int(FSH)
    deriv = np.asarray(resample_poly(deriv48, up, down), dtype=np.float64)
    flow = np.asarray(resample_poly(flow48, up, down), dtype=np.float64)

    return LfPulse(
        n1=n1,
        n2=n2,
        te=te,
        ee_gain=ee_gain,
        deriv48=deriv48,
        flow48=flow48,
        deriv=deriv,
        flow=flow,
    )
