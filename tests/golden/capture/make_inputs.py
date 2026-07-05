"""Generate the committed golden-master input fixtures.

Synthetic vowels (Rosenberg pulse train through a fixed all-pole vocal
tract), written as 16-bit PCM under ``data/fixtures/``. PCM makes the
committed bytes the single source of truth: MATLAB's ``audioread`` and
voicekit's ``read_wav`` both scale int16 by 2**15, so the two sides of
every golden-master comparison read bit-identical floats.

Inputs are chosen so the YAGA stationary-wavelet pad/trim path is
actually exercised: `vowel_f0100_16k` has a sample count divisible by
2**3 (no padding), the other two do not.

The 8 kHz fixture additionally sets ``bypass_iaif``: the reference MATLAB
IAIF zero-pads its post-highpass tail by 512 samples, which at an 8 kHz
frame size forms fully-zero LPC frames and returns a NaN residual tail
(this is intrinsic to the reference at 8 kHz, independent of the input).
For that fixture the capture drives the SWT and later group-delay stages
with the ground-truth glottal-flow derivative (`clean_residual`) instead of
the IAIF estimate, so those stages get a clean, deterministic input while
still exercising the fs<9000 code path. The 16 kHz fixtures run the real
IAIF, which is clean there.

Deterministic by construction (no RNG). Re-running this script must
reproduce the committed files exactly; CI does not run it.
"""

from pathlib import Path

import numpy as np
import numpy.typing as npt
import scipy.signal

from voicekit.io import write_wav
from voicekit.signal import Signal

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

FORMANTS = [(500.0, 80.0), (1500.0, 120.0), (2500.0, 200.0)]

# name -> (fs, n_samples, f0 start, f0 end, bypass_iaif)
INPUTS: dict[str, tuple[int, int, float, float, bool]] = {
    "vowel_f0100_16k": (16000, 9600, 100.0, 100.0, False),  # 9600 % 8 == 0: no-pad
    "vowel_glide_16k": (16000, 8837, 100.0, 150.0, False),  # 8837 % 8 == 5: pad/trim
    "vowel_f0120_8k": (8000, 4801, 120.0, 120.0, True),  # 4801 % 8 == 1: pad + fs<9000
}


def rosenberg_pulse(t0: int) -> npt.NDArray[np.float64]:
    """One Rosenberg glottal flow pulse of t0 samples (open 40%, return 16%)."""
    t1, t2 = int(0.4 * t0), int(0.16 * t0)
    pulse = np.zeros(t0)
    pulse[:t1] = 0.5 * (1 - np.cos(np.pi * np.arange(t1) / t1))
    pulse[t1 : t1 + t2] = np.cos(np.pi * np.arange(t2) / (2 * t2))
    return pulse


def glottal_flow(fs: int, n: int, f0_start: float, f0_end: float) -> npt.NDArray[np.float64]:
    """Pulse train whose period follows a linear F0 trajectory."""
    pulses = []
    pos = 0
    while pos < n:
        f0 = f0_start + (f0_end - f0_start) * pos / n
        pulses.append(rosenberg_pulse(int(round(fs / f0))))
        pos += len(pulses[-1])
    return np.concatenate(pulses)[:n]


def synth_vowel(
    fs: int, n: int, f0_start: float, f0_end: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Return (speech, glottal-flow-derivative) for a synthetic vowel.

    ``speech`` is the flow derivative through a fixed all-pole vocal tract,
    peak-normalized. The returned derivative is the exact excitation of that
    speech (its ground-truth residual), used to drive stages that bypass IAIF.
    """
    udash = np.diff(glottal_flow(fs, n, f0_start, f0_end), prepend=0.0)
    poles: list[complex] = []
    for f, bw in FORMANTS:
        if f < 0.45 * fs:
            r = np.exp(-np.pi * bw / fs)
            poles += [r * np.exp(2j * np.pi * f / fs), r * np.exp(-2j * np.pi * f / fs)]
    speech = scipy.signal.lfilter([1.0], np.poly(poles).real, udash)
    peak = np.max(np.abs(speech))
    # Same expression as the originally committed inputs, so the speech wav
    # bytes are unchanged; the residual is scaled by the identical factor.
    return np.asarray(0.95 * speech / peak), np.asarray(0.95 * udash / peak)


def clean_residual(name: str) -> npt.NDArray[np.float64] | None:
    """Ground-truth residual for a ``bypass_iaif`` fixture, else None.

    Scaled the same as the speech so its amplitude is realistic. Used by the
    capture to feed the reference SWT stage a clean input in place of the
    NaN-prone 8 kHz IAIF estimate.
    """
    fs, n, f0s, f0e, bypass = INPUTS[name]
    if not bypass:
        return None
    _, udash = synth_vowel(fs, n, f0s, f0e)
    return udash


def main() -> None:
    for name, (fs, n, f0s, f0e, _bypass) in INPUTS.items():
        speech, _ = synth_vowel(fs, n, f0s, f0e)
        path = FIXTURES_DIR / f"{name}.wav"
        write_wav(Signal(samples=speech, fs=fs), path)
        print(f"wrote {path} ({n} samples @ {fs} Hz, n % 8 == {n % 8})")


if __name__ == "__main__":
    main()
