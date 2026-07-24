"""Input conditioning for the voicing detector: the helper and the check.

`voicekit.vuv` states a **precondition** on its input (see the package
docstring, which is the canonical statement -- this module does not restate
it). This module provides the two halves of VUV12's ratified
"P3 with enforcement":

  - `condition()` -- an **explicit** helper the caller may apply to *meet* the
    precondition. The detector never calls it: conditioning is the caller's
    act, which is what keeps the detector's input-neutrality (VUV6) intact.
  - `check_precondition()` -- a **read-only** check that the detector runs to
    *enforce* the precondition. It reads its input and never rewrites it.

The helper reproduces Atal & Rabiner (1976) Eq. (1), the 200 Hz high-pass the
paper applies **before all five features** (its Fig. 1 order is scale -> HPF ->
block -> measurements). The reference dropped that preprocessing and
compensated only ``alp1``/``Ep`` via a DC-offset LPC, so ``C1``/``r1`` read a
raw frame (REFERENCE_NOTES VUV10/VUV12).

**Why conditioning cannot be left to a threshold.** Mains hum is not noise
colour but a *periodicity impostor*: 50 Hz at 16 kHz has lag-1 correlation
cos(2*pi*50/16000) ~= 0.9998 **and is genuinely periodic**, so no threshold on
any correlation statistic rejects it, at any alpha, ever. Once hum is in the
frame it is undetectable downstream by construction. The defense exists only at
the input boundary -- which is why the check is load-bearing rather than
hygiene (VUV12).

**Scope.** Conditioning discharges the 0 Hz end (DC, hum, rumble). It does
**not** touch the mid-band colour that sets the detector's operating envelope
(VUV1 J2, docs/vuv_rho_env.md): the paper's own silence class measured
C1 = 0.649 *after* this very filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import numpy.typing as npt
from scipy.signal import lfilter

from voicekit.signal import Signal

# The precondition's band edge: energy below this is "sub-speech-band" and is
# not attributable to phonation. Provenance is PHYSIOLOGICAL -- the modal
# phonation floor -- and is deliberately NOT the helper's 200 Hz corner, which
# sits above most speakers' F0: a check at the filter's corner would flag every
# low-pitched voice as violating. Single-sourced here; docs quote it, and the
# check is its only consumer.
SUB_SPEECH_BAND_HZ = 70.0

# DC check threshold on |mean|/rms. For a zero-mean process the sample mean has
# SD sigma/sqrt(N), so |mean|/rms ~= 1/sqrt(N) ~ 0.008 at N = 16000; 0.1 is
# >10x that. Statistical provenance, generous margin, no fixture.
DC_MEAN_RMS_MAX = 0.1

# Sub-band energy fraction the check tolerates. The discriminator is
# STRUCTURAL, not this number: hum/rumble is present in every frame including
# silences, while F0 energy is intermittent and mostly carried by harmonics
# above the fundamental -- so a globally-integrated sub-70 Hz fraction
# separates them without needing a sharp threshold. Generous by intent.
SUB_BAND_ENERGY_FRACTION_MAX = 0.1


@dataclass(frozen=True)
class ConditioningConfig:
    """Config for `condition` -- the paper's Eq. (1) filter.

    ``a_hz``/``b_hz`` follow the paper's own naming: its constants are
    ``a = 130*2*pi`` and ``b = 200*2*pi`` rad/s. In resonator terms the poles
    sit at radius ``exp(-a/fs)`` and angle ``b/fs``: a **200 Hz pole with
    260 Hz bandwidth**, combined with the numerator's double zero at DC. The
    numerator is not parameterized -- ``[1, -2, 1]`` *is* the DC zero, and is
    what makes the filter high-pass.

    **Changing these defaults leaves two provenances at once**, which is why
    they are documented together (docs/vuv_rho_env.md, caveat (a)/(b)):
    the paper's (the filter is cited, not chosen), and **rho_env's Table-I
    provenance** -- Table I's class statistics describe speech conditioned by
    Eq. (1) *specifically*, so a different corner puts the input outside the
    chain the operating envelope's supporting constraint was measured on.
    """

    a_hz: float = 130.0  # paper: a = 130*2*pi rad/s -> pole bandwidth 260 Hz
    b_hz: float = 200.0  # paper: b = 200*2*pi rad/s -> pole frequency 200 Hz


def eq1_coefficients(
    fs: float, config: ConditioningConfig | None = None
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """The paper's Eq. (1) as ``(b, a)`` filter coefficients at ``fs``.

    Eq. (1) is

        H(z) = (1 - 2 z^-1 + z^-2)
               / (1 - 2 exp(-aT) cos(bT) z^-1 + exp(-2aT) z^-2)

    with ``a = 130*2*pi``, ``b = 200*2*pi``, ``T = 1e-4``. **The generalization
    to arbitrary fs is established from the reference, not reconstructed**
    (VUV10): the prior research code transcribed this filter as

        hb=[1 -2 1];
        ha=[1 -2*exp(-130*2*pi/fs)*cos(200*2*pi/fs) exp(-2*130*2*pi/fs)];

    i.e. ``T -> 1/fs`` with ``a``, ``b`` fixed in rad/s -- consistent with the
    paper, whose ``T = 1e-4`` is exactly the sampling period at its own 10 kHz.
    The consequence is that the *analog* prototype is fs-invariant: the same
    200 Hz/260 Hz resonator at every rate.

    (The paper prints the numerator as ``1 - 2z^-1 + z^2``; the reference's
    ``[1 -2 1]`` confirms ``z^-2`` was meant -- a double zero at DC, without
    which the filter would not be high-pass.)
    """
    cfg = config if config is not None else ConditioningConfig()
    a = cfg.a_hz * 2.0 * np.pi
    b = cfg.b_hz * 2.0 * np.pi
    t = 1.0 / float(fs)
    num = np.array([1.0, -2.0, 1.0], dtype=np.float64)
    den = np.array(
        [1.0, -2.0 * np.exp(-a * t) * np.cos(b * t), np.exp(-2.0 * a * t)],
        dtype=np.float64,
    )
    return num, den


def condition(signal: Signal, config: ConditioningConfig | None = None) -> Signal:
    """High-pass ``signal`` with the paper's Eq. (1) -- returns a **new** Signal.

    An **explicit** helper: the detector never calls this. Applying it is the
    caller's act, which is what preserves the detector's input-neutrality
    (VUV6) -- the detector analyzes what it is handed and refuses what it
    cannot answer, rather than silently rewriting its input.

    It removes DC exactly (double zero at z = 1) and attenuates hum heavily
    (~ -27 dB at 50 Hz, ~ -24 dB at 60 Hz, relative to 1 kHz). It **attenuates
    rather than annihilates** a low fundamental (~ -16.7 dB at 90 Hz, -11.5 dB
    at 120 Hz, -4.4 dB at 180 Hz): ``r1`` does not need the fundamental, since
    its voiced value comes from spectral tilt carried through harmonics and
    formants -- the paper's own Table I measured voiced C1 = 0.881 *with* this
    filter in the chain, on a corpus including male speakers.

    Applying it is **sufficient** to meet the precondition but not
    **necessary**: the precondition is a property of the signal (see the
    package docstring), and any equivalent high-pass -- or a signal that never
    had DC or rumble, as synthetic fixtures do not -- meets it equally.

    Note the filter is not unity-gain. That is immaterial to ``r1``, which is
    scale-invariant, but it would shift a log-energy measure.
    """
    num, den = eq1_coefficients(signal.fs, config)
    x = np.asarray(signal.samples, dtype=np.float64)
    y: npt.NDArray[np.float64] = lfilter(num, den, x)
    return Signal(samples=y, fs=signal.fs, source=signal.source)


class PreconditionReport(NamedTuple):
    """What `check_precondition` measured. Diagnostic; carries no verdict."""

    mean_rms_ratio: float
    sub_band_energy_fraction: float
    dc_violation: bool
    sub_band_violation: bool


def check_precondition(signal: Signal, *, enforce: bool = True) -> PreconditionReport:
    """Check the `voicekit.vuv` precondition. **Reads; never rewrites.**

    Returns what it measured and, when ``enforce`` is true, **raises on DC**
    and **warns on sub-band** energy. That asymmetry is deliberate:
    enforcement tracks the checks' confidence. The DC check is statistically
    solid (a zero-mean signal gives ``|mean|/rms ~ 1/sqrt(N) ~ 0.008``, against
    a 0.1 threshold -- a >10x margin), so raising on it is safe. The sub-band
    threshold is shakier, and raising on it would buy false-raises on
    legitimate corpus data at Track B.

    **The named cost, stated plainly: hum only warns.** A loud warning on a
    real hazard beats a raise that gets suppressed wholesale because it
    false-fires. Both paths are escapable only *explicitly* (``enforce=False``,
    or catching the warning), so "ignored" becomes "decided" -- which is the
    whole of VUV12's "P3 with enforcement".

    ``enforce=False`` measures and reports without raising or warning: the
    explicit opt-out. It is the caller's decision, on the record in their code.
    """
    x = np.asarray(signal.samples, dtype=np.float64)
    report = _measure(x, float(signal.fs))
    if enforce:
        if report.dc_violation:
            raise ValueError(
                "voicekit.vuv precondition violated: input carries a DC offset "
                f"(|mean|/rms = {report.mean_rms_ratio:.3f} > {DC_MEAN_RMS_MAX}). "
                "DC drives r1 toward 1 and reads as fully voiced. Apply "
                "voicekit.vuv.condition() (or an equivalent high-pass), or pass "
                "enforce=False to proceed deliberately."
            )
        if report.sub_band_violation:
            import warnings

            warnings.warn(
                "voicekit.vuv precondition violated: "
                f"{report.sub_band_energy_fraction:.1%} of input energy lies below "
                f"{SUB_SPEECH_BAND_HZ:g} Hz, which phonation does not explain "
                "(mains hum or rumble). Hum is periodic, so no voicing threshold "
                "can reject it downstream. Apply voicekit.vuv.condition() (or an "
                "equivalent high-pass).",
                UserWarning,
                stacklevel=2,
            )
    return report


def _measure(x: npt.NDArray[np.float64], fs: float) -> PreconditionReport:
    """Measure both precondition quantities. Pure; touches nothing."""
    n = len(x)
    total = float(x @ x)
    if n == 0 or total == 0.0:
        # Empty or all-zero: no DC, no sub-band energy, nothing to violate.
        # Degenerate input is the finiteness predicate's business (VUV1 J1).
        return PreconditionReport(0.0, 0.0, False, False)

    rms = np.sqrt(total / n)
    mean_rms_ratio = float(abs(x.mean()) / rms)

    # Sub-band energy fraction by Parseval, integrated over the WHOLE signal:
    # the discriminator is that hum/rumble persists through every frame
    # including silences, while F0 energy is intermittent and mostly above the
    # fundamental. A global fraction separates them structurally.
    spectrum = np.fft.rfft(x)
    power = spectrum.real**2 + spectrum.imag**2
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    sub_band_fraction = float(power[freqs < SUB_SPEECH_BAND_HZ].sum() / power.sum())

    return PreconditionReport(
        mean_rms_ratio=mean_rms_ratio,
        sub_band_energy_fraction=sub_band_fraction,
        dc_violation=mean_rms_ratio > DC_MEAN_RMS_MAX,
        sub_band_violation=sub_band_fraction > SUB_BAND_ENERGY_FRACTION_MAX,
    )
