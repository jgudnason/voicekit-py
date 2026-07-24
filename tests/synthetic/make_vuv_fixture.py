"""Generate the synthetic V/UV/S ground-truth fixture for step 7 (VUV).

This is a *define-the-target* artifact, **not** a MATLAB golden-master capture.
Step 7 has no canonical voicing behaviour to match (see the fork verdict in the
step-7 handoff), so its primary oracle is a synthetic signal whose voiced /
unvoiced / silent structure is *constructed* and therefore exactly known. This
generator produces that signal and its ground-truth labels; nothing here scores
a detector.

What is emitted (all committed, deterministic by fixed seed):
  - ``<name>.wav``            : the signal, 16-bit PCM (bytes are the source of
                               truth, same convention as the golden inputs).
  - ``<name>.labels.npz``     : two independent ground-truth channels ---
      * region table (PRIMARY): ``region_start`` / ``region_end`` (sample
        indices, start-inclusive / end-exclusive) and ``region_class``
        (``'S'``/``'U'``/``'V'``). Covers *all* of S/U/V, including regions
        that contain no glottal cycles. This is the oracle.
      * voiced-only GCI list (SECONDARY): ``gci``, the true glottal-closure
        sample positions inside the V regions, known by construction. Only
        meaningful in V spans; usable by a per-cycle path *if* that framing is
        later chosen. It cannot see S or U regions.
    See ``README.md`` for why that asymmetry matters (a scorer that reads only
    ``gci`` would silently reintroduce a per-cycle framing this gate has not
    chosen).

Content construction:
  - V  : the existing sustained-vowel synthesis (``make_inputs.synth_vowel`` ---
         Rosenberg pulse train through a fixed all-pole tract), so voiced spans
         match the steps 1--6 material and the GCIs are known by construction.
  - U  : white Gaussian noise --- aperiodic, no glottal source, no true GCIs.
  - S  : a low-level Gaussian noise *floor* (ratified lean 4a: not true zero,
         which would reintroduce the log-energy=-inf / undefined-autocorrelation
         degeneracies the C7 ledger already tracks; that is a separate
         degenerate-edge fixture, not this one).

Transitions are sharp region boundaries (ratified lean 4b). The don't-care
guard band around each transition lives in *scoring*, not in this signal or its
labels; its width couples to frame length and is deferred to the next gate, so
the region table stores exact boundaries and nothing here applies a guard band.

Determinism: the voiced spans are RNG-free; only the U and S noise use the
seeded generator. Re-running reproduces the committed files exactly. CI does
not run this script.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

# Reuse the golden-input vowel synthesis without editing it. The capture tooling
# is imported the same way capture_golden.py does (its own directory on path),
# so no golden-path file is touched.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "golden" / "capture"))
import make_inputs  # noqa: E402

from voicekit.io import write_wav  # noqa: E402
from voicekit.signal import Signal  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent

# Fixed seed: the only randomness is the U/S noise; this pins the committed bytes.
SEED = 7

# Level of each noise region as a fraction of the voiced RMS. These are generator
# parameters, not resolved acoustic choices: U sits well above the floor, S is a
# quiet floor that still survives 16-bit quantization (frac * voiced_rms * 32767
# is many counts, not zero).
UV_RMS_FRAC = 0.30
SIL_RMS_FRAC = 0.005


@dataclass(frozen=True)
class Region:
    """One planned region: its class and duration; ``f0`` set only for V."""

    cls: str  # 'S', 'U', or 'V'
    dur_ms: float
    f0: float | None = None


@dataclass(frozen=True)
class FixtureSpec:
    """A complete fixture design. Adding an 8 kHz or two-f0 variant is a new
    spec here plus a line in ``main`` --- deliberately cheap, because rate
    coverage and an f0-independence variant are open questions for the gate."""

    name: str
    fs: int
    plan: tuple[Region, ...]


# The primary fixture: S -> V -> UV -> V -> S at 16 kHz, both V spans at the same
# f0 (the two-different-f0 f0-independence probe is left as a possible *second*
# fixture, an open question, not smuggled in here). 16 kHz avoids the reference
# IAIF's 8 kHz NaN tail, so the signal can later be run through the real
# front-end unmodified.
PRIMARY = FixtureSpec(
    name="vuv_svuvs_16k",
    fs=16000,
    plan=(
        Region("S", 150.0),
        Region("V", 200.0, f0=100.0),
        Region("U", 150.0),
        Region("V", 200.0, f0=100.0),
        Region("S", 150.0),
    ),
)


def _voiced_region(
    fs: int, n: int, f0: float
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64]]:
    """Return (speech, local_gci) for one voiced span of ``n`` samples.

    ``speech`` is the reused synthetic vowel. ``local_gci`` are the closure
    instants (sample of steepest flow-derivative return, i.e. ``argmin`` of the
    flow derivative within each *complete* glottal cycle), relative to the span
    start. One GCI per complete cycle; a truncated final cycle contributes none.
    """
    speech, udash = make_inputs.synth_vowel(fs, n, f0, f0)
    period = int(round(fs / f0))
    # Constant f0 => glottal_flow lays down cycles exactly ``period`` apart.
    assert period > 0
    gci = []
    for start in range(0, n, period):
        end = start + period
        if end > n:  # incomplete trailing cycle: no complete closure
            break
        gci.append(start + int(np.argmin(udash[start:end])))
    return speech, np.asarray(gci, dtype=np.int64)


def build(spec: FixtureSpec) -> tuple[Signal, dict[str, npt.NDArray[object]]]:
    """Assemble the signal and its ground-truth label arrays for ``spec``."""
    rng = np.random.default_rng(SEED)
    fs = spec.fs

    # First pass: synthesize the voiced spans so their RMS sets the noise levels.
    durations = [int(round(r.dur_ms * fs / 1000.0)) for r in spec.plan]
    voiced_parts: dict[int, tuple[npt.NDArray[np.float64], npt.NDArray[np.int64]]] = {}
    for i, (r, n) in enumerate(zip(spec.plan, durations, strict=True)):
        if r.cls == "V":
            assert r.f0 is not None, "V region needs an f0"
            voiced_parts[i] = _voiced_region(fs, n, r.f0)
    voiced_rms = float(np.sqrt(np.mean(np.concatenate([s for s, _ in voiced_parts.values()]) ** 2)))

    # Second pass: lay out every region, accumulating the signal and labels.
    pieces: list[npt.NDArray[np.float64]] = []
    r_start, r_end, r_cls = [], [], []
    gci_all: list[int] = []
    pos = 0
    for i, (r, n) in enumerate(zip(spec.plan, durations, strict=True)):
        if r.cls == "V":
            samples, local_gci = voiced_parts[i]
            gci_all.extend((pos + local_gci).tolist())
        elif r.cls == "U":
            samples = rng.standard_normal(n) * (UV_RMS_FRAC * voiced_rms)
        elif r.cls == "S":
            samples = rng.standard_normal(n) * (SIL_RMS_FRAC * voiced_rms)
        else:
            raise ValueError(f"unknown region class {r.cls!r}")
        pieces.append(np.asarray(samples, dtype=np.float64))
        r_start.append(pos)
        r_end.append(pos + n)
        r_cls.append(r.cls)
        pos += n

    full = np.concatenate(pieces)
    labels = {
        "region_start": np.asarray(r_start, dtype=np.int64),
        "region_end": np.asarray(r_end, dtype=np.int64),
        "region_class": np.asarray(r_cls),  # unicode 'S'/'U'/'V'
        "gci": np.asarray(sorted(gci_all), dtype=np.int64),
        "fs": np.asarray(fs, dtype=np.int64),
    }
    _check(full, labels)
    return Signal(samples=full, fs=fs, source=spec.name), labels


def _check(full: npt.NDArray[np.float64], labels: dict[str, npt.NDArray[object]]) -> None:
    """Fail generation if the artifact is not internally well-formed.

    These are fixture-integrity invariants (framing-neutral), asserted at build
    time so the committed files are provably consistent. They score no detector.
    """
    n = len(full)
    rs = labels["region_start"].astype(np.int64)
    re = labels["region_end"].astype(np.int64)
    rc = labels["region_class"]
    gci = labels["gci"].astype(np.int64)

    assert np.max(np.abs(full)) <= 1.0, "signal exceeds [-1, 1]"
    assert set(rc.tolist()) <= {"S", "U", "V"}, "unexpected region class"
    # The regions partition [0, n) with no gap or overlap.
    assert rs[0] == 0 and re[-1] == n, "regions must span the whole signal"
    assert np.array_equal(rs[1:], re[:-1]), "regions must be contiguous"
    assert np.all(re > rs), "every region must be non-empty"
    # Every GCI lies strictly inside some V region; the list is voiced-only.
    v_lo = rs[rc == "V"]
    v_hi = re[rc == "V"]
    assert np.all(np.diff(gci) > 0), "GCIs must be strictly increasing"
    for g in gci:
        assert np.any((v_lo <= g) & (g < v_hi)), f"GCI {g} not inside a V region"


def main() -> None:
    signal, labels = build(PRIMARY)
    wav_path = OUT_DIR / f"{PRIMARY.name}.wav"
    npz_path = OUT_DIR / f"{PRIMARY.name}.labels.npz"
    write_wav(signal, wav_path)
    np.savez(npz_path, **labels)
    n = signal.n_samples
    n_v = int(
        np.sum(
            labels["region_end"][labels["region_class"] == "V"]
            - labels["region_start"][labels["region_class"] == "V"]
        )
    )
    print(f"wrote {wav_path} ({n} samples @ {PRIMARY.fs} Hz)")
    print(f"wrote {npz_path} ({len(labels['gci'])} GCIs across {n_v} voiced samples)")


if __name__ == "__main__":
    main()
