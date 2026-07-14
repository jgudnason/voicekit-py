"""Generate the discriminating V/non-V fixtures (D1/D2/D3) for step 7 (VUV).

These are the *hard-case* oracles, sibling to the clean-separation floor fixture
(`make_vuv_fixture.py`). They exist so the voicing detector is tested where a
naive energy rule fails, and — unlike the floor fixture — one of them (D1)
deliberately places a real glottal closure in a non-voiced region so the derived
per-cycle mask is actually exercised.

Ground-truth label (feature-free, by construction): a region is **voiced** iff a
quasi-periodic glottal source component was summed into its samples; otherwise
**non-voiced**. The label references no measured quantity (not energy, zero
crossings, autocorrelation, prediction, tilt). Binary, per the architecture gate.

Two independent channels are committed, as for the floor fixture:
  - region table (PRIMARY): ``region_start`` / ``region_end`` (start-inclusive,
    end-exclusive), ``region_label`` (``'V'``/``'N'``), plus ``region_kind`` (a
    descriptive construction tag) and ``region_hard_param`` (the per-region
    hard-regime metadata: D1 SNR dB, D2 VFR dB, D3 HNR dB — a *stratification*
    channel, not a label and not a threshold).
  - construction GCI list (SECONDARY): the source closures known by construction.
    Note: D1's mask-exercise assertion runs against the GCIs YAGA *detects*, not
    this list; the list is reference metadata.

D1 (this module, first): low-energy voiced offset decaying through the floor,
with a two-instant offset — the voiced->non-voiced label boundary ``t3`` precedes
the source switch-off ``t_src_off``, so real closures fall in the sub-floor
non-voiced tail. See ``README.md`` and REFERENCE_NOTES "Step 7 (VUV)".

Deterministic by fixed seed (only the noise draws are random). CI does not run
this script.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import scipy.signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "golden" / "capture"))
import make_inputs  # noqa: E402

from voicekit.io import write_wav  # noqa: E402
from voicekit.signal import Signal  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
SEED = 7


@dataclass(frozen=True)
class Region:
    """One region of a discriminating fixture."""

    start: int
    end: int
    label: str  # 'V' or 'N' — the binary ground truth
    kind: str  # descriptive construction tag
    hard_param: float  # per-region hard-regime metadata (SNR/VFR/HNR dB)


def _source_closures(udash: npt.NDArray[np.float64], fs: int, f0: float) -> npt.NDArray[np.int64]:
    """Closure sample of each complete glottal cycle (argmin of the derivative)."""
    period = int(round(fs / f0))
    gci = [
        start + int(np.argmin(udash[start : start + period]))
        for start in range(0, len(udash), period)
        if start + period <= len(udash)
    ]
    return np.asarray(gci, dtype=np.int64)


def _db_to_amp(snr_db: float) -> float:
    return float(10.0 ** (snr_db / 20.0))


def build_d1(fs: int = 16000) -> tuple[Signal, list[Region], npt.NDArray[np.int64], str]:
    """D1 — low-energy voiced offset decaying through the noise floor.

    A voiced segment (steady -> exponential decay) sits on a stationary noise
    floor present everywhere. The label boundary ``t3`` (voiced_decay -> the
    non-voiced ``subfloor_residual``) is placed *before* the source switch-off,
    so the pulse train keeps emitting closures into the sub-floor tail: those
    closures are real, live-detectable, and lie in a region the ground truth
    labels non-voiced. That is the derived mask's exercise.
    """
    f0 = 120.0
    ms = lambda t: int(round(t * fs / 1000.0))  # noqa: E731
    n_lead, n_steady, n_decay, n_sub, n_trail = ms(100), ms(150), ms(150), ms(70), ms(100)
    n_src = n_steady + n_decay + n_sub  # source-on span (steady + decay + sub-floor)

    # Voiced source over the whole source-on span; peak-normalized speech + udash.
    speech, udash = make_inputs.synth_vowel(fs, n_src, f0, f0)
    rms_v = float(np.sqrt(np.mean(speech**2)))
    closures = _source_closures(udash, fs, f0)

    # SNR schedule (dB), by construction: steady flat high, then exponential decay
    # continuing monotonically across the label boundary into the sub-floor tail.
    snr_steady, snr_t3, snr_end = 30.0, -2.0, -16.0
    env = np.ones(n_src)
    dec = np.concatenate([
        np.linspace(snr_steady, snr_t3, n_decay, endpoint=False),
        np.linspace(snr_t3, snr_end, n_sub),
    ])
    env[n_steady:] = np.array([_db_to_amp(s - snr_steady) for s in dec])  # amp rel to steady

    sigma_n = rms_v * _db_to_amp(-snr_steady)  # floor: steady sits at +snr_steady dB
    rng = np.random.default_rng(SEED)
    n_total = n_lead + n_src + n_trail
    x = rng.standard_normal(n_total) * sigma_n  # floor everywhere
    x[n_lead : n_lead + n_src] += env * speech  # add the enveloped voiced source

    # Region table. t3 = start of subfloor_residual; t_src_off = its end.
    off_steady = n_lead
    off_decay = off_steady + n_steady
    t3 = off_decay + n_decay
    t_src_off = t3 + n_sub
    regions = [
        Region(0, n_lead, "N", "floor_lead", -np.inf),
        Region(off_steady, off_decay, "V", "voiced_steady", snr_steady),
        Region(off_decay, t3, "V", "voiced_decay", (snr_steady + snr_t3) / 2),
        Region(t3, t_src_off, "N", "subfloor_residual", (snr_t3 + snr_end) / 2),
        Region(t_src_off, n_total, "N", "floor_trail", -np.inf),
    ]
    # Construction closures shifted into signal coordinates.
    gci_construction = closures + n_lead
    peak = float(np.max(np.abs(x)))
    x = x / peak * 0.95  # global normalize into [-1, 1)
    return Signal(samples=x, fs=fs, source="vuv_d1_offset_16k"), regions, gci_construction, "snr_db"


def _bandlimited_noise(rng: np.random.Generator, n: int, fs: int,
                       lo: float, hi: float) -> npt.NDArray[np.float64]:
    """Unit-RMS Gaussian noise band-limited to [lo, hi] Hz (Butterworth band-pass)."""
    b, a = scipy.signal.butter(4, [lo / (fs / 2), hi / (fs / 2)], btype="band")
    y = scipy.signal.lfilter(b, a, rng.standard_normal(n))
    return np.asarray(y / np.sqrt(np.mean(y**2)))


def build_d2(fs: int = 16000) -> tuple[Signal, list[Region], npt.NDArray[np.int64], str]:
    """D2 — voiced frication: matched source-on / source-off under identical turbulence.

    Regions ``voiced_fricative`` (source + band-limited turbulence) and
    ``unvoiced_fricative`` (turbulence only, same band/level) share their noise
    statistics, so energy and zero-crossing rate cannot separate them; only the
    periodic component (present in the first, absent in the second) can. The label
    is source-presence, not any measured quantity.
    """
    f0 = 150.0
    ms = lambda t: int(round(t * fs / 1000.0))  # noqa: E731
    n_modal, n_vfric, n_ufric = ms(120), ms(150), ms(150)
    vfr_db = -10.0  # voicing-to-frication ratio: turbulence dominates (so Nz converges too)

    speech_m, udash_m = make_inputs.synth_vowel(fs, n_modal, f0, f0)
    speech_v, udash_v = make_inputs.synth_vowel(fs, n_vfric, f0, f0)
    rms_v = float(np.sqrt(np.mean(np.concatenate([speech_m, speech_v]) ** 2)))
    fric_rms = rms_v * _db_to_amp(-vfr_db)  # turbulence louder than voicing when vfr<0

    rng = np.random.default_rng(SEED)
    # One shared turbulence realization across the matched pair: the non-voiced
    # partner is the SAME noise waveform, energy-matched to the voiced region's
    # total power. So the pair differs ONLY by the added source -- no seed-slice
    # artifact -- and energy is exactly equal. Any residual zero-crossing gap is
    # then purely the intrinsic effect of superimposing the periodic source.
    assert n_vfric == n_ufric
    turb = _bandlimited_noise(rng, n_vfric, fs, 2000.0, 7000.0)  # unit RMS
    voiced_fric = speech_v + turb * fric_rms
    matched_rms = float(np.sqrt(np.mean(voiced_fric**2)))
    unvoiced_fric = turb * matched_rms

    x = np.concatenate([speech_m, voiced_fric, unvoiced_fric])
    o1, o2, o3 = n_modal, n_modal + n_vfric, n_modal + n_vfric + n_ufric
    regions = [
        Region(0, o1, "V", "voiced_modal", np.inf),  # no frication -> VFR = +inf
        Region(o1, o2, "V", "voiced_fricative", vfr_db),
        Region(o2, o3, "N", "unvoiced_fricative", -np.inf),  # no voicing -> VFR = -inf
    ]
    gci_construction = np.concatenate([
        _source_closures(udash_m, fs, f0),
        _source_closures(udash_v, fs, f0) + n_modal,
    ])
    peak = float(np.max(np.abs(x)))
    x = x / peak * 0.95
    return Signal(samples=x, fs=fs, source="vuv_d2_vfric_16k"), regions, gci_construction, "vfr_db"


def _spectral_tilt(x: npt.NDArray[np.float64], a: float) -> npt.NDArray[np.float64]:
    """One-pole low-pass: steepens the high-frequency roll-off (breathier timbre)."""
    return np.asarray(scipy.signal.lfilter([1.0 - a], [1.0, -a], x))


def build_d3(fs: int = 16000) -> tuple[Signal, list[Region], npt.NDArray[np.int64], str]:
    """D3 — breathy voice: weak tilted source under aspiration, matched on/off.

    ``modal_voiced`` (low tilt) and ``breathy_voiced`` (high tilt + aspiration)
    are both source-present -> label V, so spectral tilt varies *within* the
    voiced class and cannot proxy the label. ``breathy_voiced`` and ``aspiration``
    share identical noise, so energy and zero-crossings cannot separate them; only
    the (weak) periodic component can, at HNR ~ 0 dB.
    """
    f0 = 180.0
    ms = lambda t: int(round(t * fs / 1000.0))  # noqa: E731
    n_modal, n_breathy, n_asp = ms(120), ms(150), ms(150)
    hnr_db = 0.0  # harmonics-to-noise ratio (hard regime: comparable powers)

    speech_m, udash_m = make_inputs.synth_vowel(fs, n_modal, f0, f0)
    speech_b0, udash_b = make_inputs.synth_vowel(fs, n_breathy, f0, f0)
    speech_b = _spectral_tilt(speech_b0, 0.72)  # breathy: steeper HF roll-off, higher tilt
    rms_b = float(np.sqrt(np.mean(speech_b**2)))
    asp_rms = rms_b * _db_to_amp(-hnr_db)

    rng = np.random.default_rng(SEED)
    # Shared aspiration realization across the matched pair (see build_d2): the
    # non-voiced partner is the same noise, energy-matched, so the pair differs
    # only by the weak breathy source.
    assert n_breathy == n_asp
    asp = _bandlimited_noise(rng, n_breathy, fs, 300.0, 6000.0)  # unit RMS
    breathy_voiced = speech_b + asp * asp_rms
    matched_rms = float(np.sqrt(np.mean(breathy_voiced**2)))
    aspiration = asp * matched_rms

    x = np.concatenate([speech_m, breathy_voiced, aspiration])
    o1, o2, o3 = n_modal, n_modal + n_breathy, n_modal + n_breathy + n_asp
    regions = [
        Region(0, o1, "V", "modal_voiced", np.inf),  # no aspiration -> HNR = +inf
        Region(o1, o2, "V", "breathy_voiced", hnr_db),
        Region(o2, o3, "N", "aspiration", -np.inf),  # no voicing -> HNR = -inf
    ]
    gci_construction = np.concatenate([
        _source_closures(udash_m, fs, f0),
        _source_closures(udash_b, fs, f0) + n_modal,
    ])
    peak = float(np.max(np.abs(x)))
    x = x / peak * 0.95
    sig = Signal(samples=x, fs=fs, source="vuv_d3_breathy_16k")
    return sig, regions, gci_construction, "hnr_db"


def _write(name: str, signal: Signal, regions: list[Region],
           gci_construction: npt.NDArray[np.int64], hard_param_name: str) -> None:
    labels = {
        "region_start": np.asarray([r.start for r in regions], dtype=np.int64),
        "region_end": np.asarray([r.end for r in regions], dtype=np.int64),
        "region_label": np.asarray([r.label for r in regions]),
        "region_kind": np.asarray([r.kind for r in regions]),
        "region_hard_param": np.asarray([r.hard_param for r in regions], dtype=np.float64),
        "hard_param_name": np.asarray(hard_param_name),
        "gci_construction": np.asarray(gci_construction, dtype=np.int64),
        "fs": np.asarray(signal.fs, dtype=np.int64),
    }
    _check(signal, regions, gci_construction)
    write_wav(signal, OUT_DIR / f"{name}.wav")
    np.savez(OUT_DIR / f"{name}.labels.npz", **labels)
    print(f"wrote {name}: {signal.n_samples} samp @ {signal.fs} Hz, {len(regions)} regions")


def _check(signal: Signal, regions: list[Region], gci: npt.NDArray[np.int64]) -> None:
    n = signal.n_samples
    assert np.max(np.abs(signal.samples)) <= 1.0
    assert regions[0].start == 0 and regions[-1].end == n
    for a, b in zip(regions[:-1], regions[1:], strict=True):
        assert a.end == b.start, "regions must be contiguous"
    assert all(r.end > r.start for r in regions)
    assert all(r.label in ("V", "N") for r in regions)


def main() -> None:
    _write("vuv_d1_offset_16k", *build_d1())
    _write("vuv_d2_vfric_16k", *build_d2())
    _write("vuv_d3_breathy_16k", *build_d3())


if __name__ == "__main__":
    main()
