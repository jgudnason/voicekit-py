"""Generate the conditioning-hazard fixtures (H0-H4) for step 7 (VUV12).

These exercise the two input-conditioning hazards the ratified precondition
exists for, against the helper and check committed in 8e24d7b:

  - **DC** (H1): the tidy limit case. Drives ``r1`` toward 1 on non-voiced
    input, so noise + DC reads as confidently voiced. Trivially removable
    (the Eq. (1) filter's double zero at DC kills it exactly), and the check
    RAISES on it -- its ``|mean|/rms`` test is statistically solid.
  - **HUM** (H2): the hazard that made the check load-bearing. 50 Hz at 16 kHz
    has lag-1 correlation cos(2*pi*50/16000) = 0.99981 **and is genuinely
    periodic**, so no threshold on any correlation statistic rejects it, at any
    alpha, ever (VUV12). Only the filter removes it. The check WARNS.

**Shape: a set of single-condition signals, not one signal with regions.** This
is a deliberate departure from the D-series (D1/D2/D3), forced by granularity
and recorded here so it does not read as inconsistency: ``check_precondition``
is a **signal-global** predicate (``|mean|/rms`` and the sub-70 Hz energy
fraction integrate over the whole signal), while ``r1`` is per-frame. A "DC
region" inside a longer clean signal would have its offset diluted by
everything around it -- the check would then see a *mixture*, not the
condition it is meant to test. So each case is its own uniform signal, and the
labels file carries one row per **case** rather than the D-series' region
table.

Ground-truth label (feature-free, by construction, identical rule to the
D-series): a case is **voiced** iff a quasi-periodic glottal source was summed
into it; otherwise **non-voiced**. Note what this rule settles by itself: H2's
hum is periodic but is **not phonation**, so H2 is labelled N. That is the
impostor, stated in the ground truth rather than discovered by a measurement.

Levels are chosen for a stated reason, not tuned: ``d = 2.5*sigma`` is the
smallest round DC offset that drives ``r1`` above the *entire* declared rho_env
range (0.53-0.81, docs/vuv_rho_env.md), so the false-voiced reading is
unambiguous rather than marginal; hum at 3x noise RMS does the same for H2
(clearing 0.81 needs hum RMS > 2.06*sigma).

Deterministic by fixed seed. ``SEED = 11`` is deliberately **not** the
D-series' ``SEED = 7``: the two fixture families then draw independent noise
realizations, so no accidental coupling can hide between them. CI does not run
this script.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "golden" / "capture"))
import make_inputs  # noqa: E402

from voicekit.io import write_wav  # noqa: E402
from voicekit.signal import Signal  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
SEED = 11
FS = 16000
DUR_S = 0.5  # 8000 samples: 47 frames on the locked grid, 2 Hz FFT resolution
HUM_HZ = 50.0


@dataclass(frozen=True)
class Case:
    """One conditioning-hazard case: a whole signal at one condition."""

    name: str
    label: str  # 'V' or 'N' — the binary ground truth, from construction
    kind: str  # descriptive construction tag
    hazard: str  # 'none' | 'dc' | 'hum' — which hazard is present, if any


def _hum(n: int, fs: int, rms: float) -> npt.NDArray[np.float64]:
    """A 50 Hz sinusoid at the given RMS — mains hum, the periodicity impostor."""
    t = np.arange(n) / fs
    return np.sqrt(2.0) * rms * np.sin(2.0 * np.pi * HUM_HZ * t)


def build() -> list[tuple[Case, Signal]]:
    """Build all five cases. Each is peak-normalized last, as the D-series is."""
    n = int(round(DUR_S * FS))
    rng = np.random.default_rng(SEED)
    out: list[tuple[Case, Signal]] = []

    # H0 — clean voiced: the control. Nothing added.
    speech, _ = make_inputs.synth_vowel(FS, n, 120.0, 120.0)
    out.append(
        (
            Case("vuv_h0_clean_16k", "V", "clean_voiced", "none"),
            _sig(speech, "vuv_h0_clean_16k"),
        )
    )

    # H1 — DC + noise: the tidy limit. NOT DC + voiced: on voiced input r1 is
    # already ~0.99, so DC cannot make it "more voiced" and tests nothing. The
    # hazard is the false POSITIVE, which lives on non-voiced input.
    noise = rng.standard_normal(n)
    noise /= np.sqrt(np.mean(noise**2))  # unit RMS
    out.append(
        (
            Case("vuv_h1_dc_16k", "N", "dc_noise", "dc"),
            _sig(noise + 2.5, "vuv_h1_dc_16k"),
        )
    )

    # H2 — hum + noise: THE impostor. Hum is periodic but is not phonation, so
    # the construction label is N. Unconditioned r1 must read false-voiced.
    noise2 = rng.standard_normal(n)
    noise2 /= np.sqrt(np.mean(noise2**2))
    out.append(
        (
            Case("vuv_h2_hum_16k", "N", "hum_noise", "hum"),
            _sig(noise2 + _hum(n, FS, 3.0), "vuv_h2_hum_16k"),
        )
    )

    # H3 — hum + voiced: the realistic contamination. Conditioning must remove
    # the impostor's contribution without losing the voiced verdict.
    speech_h, _ = make_inputs.synth_vowel(FS, n, 120.0, 120.0)
    rms_s = float(np.sqrt(np.mean(speech_h**2)))
    out.append(
        (
            Case("vuv_h3_humvoiced_16k", "V", "hum_voiced", "hum"),
            _sig(speech_h + _hum(n, FS, rms_s), "vuv_h3_humvoiced_16k"),
        )
    )

    # H4 — low-F0 clean voiced: the check's false-positive boundary. 85 Hz is a
    # realistic low-male floor. A periodic signal's fundamental is its LOWEST
    # component, so nothing of it falls below the 70 Hz edge. No F0 < 70 case:
    # below the modal floor a signal genuinely carries sub-phonation energy, so
    # firing there is the edge working, not failing.
    speech_l, _ = make_inputs.synth_vowel(FS, n, 85.0, 85.0)
    out.append(
        (
            Case("vuv_h4_lowf0_16k", "V", "lowf0_voiced", "none"),
            _sig(speech_l, "vuv_h4_lowf0_16k"),
        )
    )

    return out


def _sig(x: npt.NDArray[np.float64], name: str) -> Signal:
    """Peak-normalize into [-1, 1) and wrap. r1 is scale-invariant; this only
    keeps the wavs well-formed (and, for H1, preserves |mean|/rms)."""
    peak = float(np.max(np.abs(x)))
    return Signal(samples=np.asarray(x / peak * 0.95), fs=FS, source=name)


def main() -> None:
    cases = build()
    for case, signal in cases:
        write_wav(signal, OUT_DIR / f"{case.name}.wav")
    np.savez(
        OUT_DIR / "vuv_h_cases.labels.npz",
        case_name=np.asarray([c.name for c, _ in cases]),
        case_label=np.asarray([c.label for c, _ in cases]),
        case_kind=np.asarray([c.kind for c, _ in cases]),
        case_hazard=np.asarray([c.hazard for c, _ in cases]),
    )
    for case, _ in cases:
        print(f"{case.name:24s} {case.label}  {case.kind:14s} hazard={case.hazard}")


if __name__ == "__main__":
    main()
