"""The voicing decision layer: the ``r1`` statistic and the voicing rule.

This module is **define-the-target**, not capture-and-match: the reference's
decision stages were rejected at the architecture gate (C's non-deterministic
GMM; E's TIMIT-trained centroids -- see REFERENCE_NOTES VUV15), so there is no
MATLAB oracle here and **no parity claim attaches to anything in this module**.
Provenance and rationale: ``docs/vuv_c1_decision.md`` (the decision record),
``docs/vuv_r1_null.md`` (the null behind the threshold), ``docs/vuv_rho_env.md``
(the colour margin).

**The classifier never touches the feature layer.** `detect_voicing` takes a
`Signal`, computes ``r1`` itself, and never calls `extract_frame_features`. A
reader will assume otherwise -- the five Atal-Rabiner features are the visible,
golden-mastered thing -- so, stated before it looks like a defect: **the shipped
detector uses none of the five.** That is the ratified fork-scoping (features are
capture-and-match reproduction; the decision is define-the-target, VUV7), and
the feature layer keeps three real jobs:

  1. **reference parity** -- it is the reproduction, gated bit-exact against the
     MATLAB oracle (VUV7), and that is its own deliverable;
  2. **substrate for a future multivariate rule** -- VUV11's guarded joint route,
     if a redistributable corpus ever makes one admissible;
  3. **it is how ``r1`` exists at all** -- reproducing ``C1`` is what exposed the
     reference's one-parenthesis broadcast bug against Atal & Rabiner Eq. (3)
     (VUV7/VUV10), and ``r1`` is that equation computed as published.

**Deliberately not here.** Label smoothing: the reference applies
``medfilt1(vus,3)`` to its *label sequence* -- the paper's 3-level contour
smoothing (VUV15). Being post-decision, it is a different question from the
pre-decision ``C1`` smoothing that VUV8 rejected, so it is **out of scope, not
foreclosed**: it would need its own provenance for the window, and the minimal
unit stays minimal. The rule here is strictly per-frame with no post-processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from scipy.special import ndtri

from voicekit.signal import Signal
from voicekit.vuv.conditioning import check_precondition
from voicekit.vuv.grid import VoicingGrid


def r1(s: npt.NDArray[np.float64], start: int, frame_len: int) -> float:
    """Normalized autocorrelation coefficient at unit sample delay -- ``r1``.

    Atal & Rabiner (1976), Eq. (3), computed as published: for the frame
    ``x = s[start : start+frame_len]`` and its one-sample-delayed partner
    ``y = s[start-1 : start+frame_len-1]``,

        r1 = <x, y> / (||x|| * ||y||)

    The boundary sample ``s[start-1]`` enters the numerator **once** and the
    denominator once, so ``r1`` is an exact normalized inner product, bounded
    in [-1, +1] by Cauchy-Schwarz ("by definition, varies between -1 and +1",
    p. 204). This is deliberately **not** the feature layer's ``C1``, which
    reproduces the reference's broadcast of the boundary term (N-1 times,
    unbounded -- VUV7/VUV8); ``r1`` is a decision-layer statistic with **no
    parity claim** (see ``docs/vuv_c1_decision.md``).

    Null (docs/vuv_r1_null.md): white noise gives E[r1] = 0, std ~ 1/sqrt(N);
    coloured noise shifts the mean to ~ rho (the noise's own lag-1
    correlation) -- the coloured-noise floor is a bias, not estimation noise.

    A zero-energy frame yields 0/0 = ``NaN``; mapping that to a label is the
    decision rule's finiteness predicate (VUV1 J1), not the statistic's.
    ``start`` must be >= 1: the frame at 0 has no boundary sample, and
    refusing it here is what prevents a silent wrap to the signal tail.

    Reference: B. S. Atal and L. R. Rabiner, "A Pattern Recognition Approach
    to Voiced-Unvoiced-Silence Classification with Applications to Speech
    Recognition," IEEE Trans. ASSP-24(3), pp. 201-212, June 1976, Eq. (3).
    """
    if start < 1:
        raise ValueError(f"r1 needs the boundary sample s[start-1]; got start={start}")
    x = s[start : start + frame_len]
    y = s[start - 1 : start + frame_len - 1]
    with np.errstate(invalid="ignore"):
        return float((x @ y) / np.sqrt((x @ x) * (y @ y)))


@dataclass(frozen=True)
class VuvConfig:
    """Config for the voicing rule: ``threshold = rho_env + z(1-alpha)/sqrt(N)``.

    The two terms are kept apart deliberately (``docs/vuv_r1_null.md``): the
    coloured-noise floor is a **bias**, not estimation noise, so no alpha makes
    ``z/sqrt(N)`` clear a rho that does not shrink with N. Collapsing them is
    how a colour margin ends up wearing a quantile's clothes.
    """

    rho_env: float
    """Upper bound on the mean ``r1`` of the aperiodic noise you expect --
    **required, with no default, and that is deliberate.**

    ``rho_env`` is a **deployment property**, not a universal constant: it is a
    claim about *your* recording environment's noise colour. Atal & Rabiner's
    Table I constrains it to roughly **0.53-0.81** at 16 kHz but **cannot pin a
    point within that range** (``docs/vuv_rho_env.md``), so any default shipped
    here would be arbitrary while reading as recommended -- and every candidate
    default is compromised in one of two ways: those that admit D3's breathy
    voice (0.625) sit at its survival boundary, which is precisely the shape of
    the ``k = 1`` choice that document already retracted; those that exclude it
    decide your noise environment on your behalf. Requiring it removes the free
    parameter rather than defending it.

    **How to get it:** measure ``r1`` over a known non-speech region of your own
    recordings -- that *is* this quantity. (A caller-declared constant is not the
    adaptive gating VUV1 rejected: the config stays explicit and typed, and the
    same config on the same input gives the same answer.)

    **Cost, stated:** the detector does not run out of the box.
    """

    alpha: float = 0.05
    """Significance level of the estimation term; ``z = ndtri(1 - alpha)``.

    0.05 is **the statistical convention, named as a convention and not derived**
    -- the white null gives the *form* ``z/sqrt(N)`` (``docs/vuv_r1_null.md``),
    never the level. Trade it knowingly: alpha is the fraction of in-envelope
    noise frames that read voiced on estimation noise alone, so at the locked
    grid's 100 frames/s, **0.05 is ~5 false-voiced frames per second**; 0.01
    gives ~1.

    It cannot carry the decision, which is structural rather than lucky: with
    ``rho_env`` required, alpha alone determines no fixture outcome, and across
    0.05 -> 0.001 it moves the threshold by only ~0.06 against ``rho_env``'s
    0.28-wide range. This is the knob the fit hid in first (z ~ 6.1, whose
    6.1/sqrt(512) = 0.270 was numerically D3's measured aspiration colour).
    """

    grid: VoicingGrid = field(default_factory=VoicingGrid)
    """The locked 32 ms / 10 ms voicing grid (VUV6). Its own config, not IAIF's."""

    enforce_precondition: bool = True
    """Run `check_precondition` on the input: raise on DC, warn on sub-band
    energy (VUV12). ``False`` is the ratified **explicit** opt-out -- it makes
    "ignored" into "decided", on the record in your code."""

    floor_dbfs: float = -90.0
    """The recording-chain floor guard (J2): a frame whose RMS is below this
    reads non-voiced and is flagged `VoicingTrack.floor_gated`. **A floor guard,
    never a speech/silence detector** (VUV1) -- a level so low it can never
    arbitrate speech content.

    The default is the **16-bit LSB amplitude** (``20*log10(2**-15) = -90.3``,
    rounded), stated against a **declared reference format of 16-bit** -- the
    honest choice for this project's corpora. It is the conservative (higher)
    end of the defensible band (16-bit quantization-noise RMS is -101 dBFS);
    higher is the safe direction for a guard that must never eat speech. Nothing
    above ~-66 dBFS is defensible under any format.

    **Rule-1 note (docs/working_method.md):** this default was fixed *before any
    fixture outcome was visible and no fixture can move it* -- the physical
    argument (16-bit LSB) predates the guard, and the ~53 dB margin to D1's real
    noise floor (-37.3 dBFS) means every committed fixture is silent to the
    guard wherever in the -100..-90 band it sits. It is a physical constant with
    a config override, not a fitted default -- and unlike `rho_env` (a per-
    environment deployment property, hence no default) this is a **format**
    constant, so 16-bit is the right thing to assume.

    **The reference-format caveat:** the detector receives float arrays and does
    not know the source bit depth. On a 24-bit or float recording, genuinely-
    recorded content between that format's true floor and this 16-bit-referenced
    guard would be pre-gated -- but speech at -90 dBFS RMS is not usable speech,
    so "never arbitrates speech" survives in practice. A caller working below
    16-bit resolution should lower ``floor_dbfs`` to their declared format's
    floor (12-bit legacy corpus: ~-66; 24-bit: lower).
    """

    def threshold(self, fs: float) -> float:
        """The decision threshold at ``fs``: ``rho_env + z(1-alpha)/sqrt(N)``."""
        n = self.grid.frame_len(fs)
        return self.rho_env + float(ndtri(1.0 - self.alpha)) / float(np.sqrt(n))


@dataclass(frozen=True)
class VoicingTrack:
    """Frame-based voicing track -- the decision layer's output.

    Primary field is `voiced`; the rest is self-describing framing plus two
    diagnostic channels. **`undefined` and `floor_gated` are diagnostics, not a
    third label**: the label domain stays binary (architecture gate), kept
    wideable for a later silence consumer.

    **Two pre-gate fields, where the architecture gate said "a field"** -- an
    extension, with its reason, so it does not read as drift. VUV1's pre-gate has
    two jobs of different standing, and they need different observability:
    `undefined` is J1 (remedial: the statistic could not be computed -- frame 0,
    or a zero-energy frame where ``r1`` is 0/0) and `floor_gated` is J2
    (principled: the frame's RMS is below the declared recording-chain floor,
    `VuvConfig.floor_dbfs`). A single combined field could not express the
    ratified **anti-creep test** -- "the floor guard must never fire on any D1
    frame" -- without special-casing frame 0, which J1 always flags. And a later
    S/U/V widening wants J2 (silence), not J1 (a degenerate frame) -- conflating
    them would hand the widening the wrong signal, so **read `floor_gated` for
    "this was silence".**

    The two fire independently and both-true is coherent: a zero frame is
    `undefined` (0/0) *and* `floor_gated` (RMS below the floor). They are not
    redundant -- a near-silence frame (~-92 dBFS, e.g. dithered/quantization-
    noise silence) has finite ``r1``, so J1 does not fire, but J2 does. J2
    catches the silence J1 structurally cannot.

    Invariant: ``voiced`` implies neither ``undefined`` nor ``floor_gated``.
    """

    voiced: npt.NDArray[np.bool_]
    undefined: npt.NDArray[np.bool_]
    floor_gated: npt.NDArray[np.bool_]
    fs: int
    frame_len: int
    hop: int

    @property
    def n_frames(self) -> int:
        return len(self.voiced)

    @property
    def frame_centers(self) -> npt.NDArray[np.float64]:
        """0-based centre sample of each frame -- derived, not stored, and by the
        same arithmetic as `VoicingGrid.frame_centers` (its single source)."""
        k = np.arange(self.n_frames)
        return np.asarray(k * self.hop + (self.frame_len - 1) / 2, dtype=np.float64)


def detect_voicing(signal: Signal, config: VuvConfig) -> VoicingTrack:
    """Per-frame voiced/non-voiced decision on ``signal``. Returns a `VoicingTrack`.

    ``config`` is required, not optional: `VuvConfig.rho_env` has no default, so
    the operating envelope must be declared rather than inherited.

    The rule, per frame: **voiced iff ``r1 > rho_env + z(1-alpha)/sqrt(N)``.**
    Strictly per-frame -- no smoothing, no post-processing (see the module
    docstring). Frames whose ``r1`` is undefined are non-voiced and flagged
    `undefined` (VUV1's J1 finiteness predicate, a fixed behaviour and not a
    knob: asserting *voiced* from an uncomputable statistic would claim
    periodicity from no evidence). Two frames are undefined: any zero-energy
    frame (0/0 -- ``r1`` inherits this, boundedness does not fix zero energy),
    and **frame 0**, which has no boundary sample. Frame 0 stays in the track --
    dropping it would desynchronise the track from the grid.

    Trailing samples that do not fill a frame are dropped, by
    `VoicingGrid.frame_centers` -- so every frame here is a full frame.

    Input must meet the `voicekit.vuv` precondition; this runs the check
    (raising on DC, warning on sub-band energy) unless
    ``config.enforce_precondition`` is False.
    """
    check_precondition(signal, enforce=config.enforce_precondition)

    s = np.asarray(signal.samples, dtype=np.float64)
    fs = float(signal.fs)
    frame_len = config.grid.frame_len(fs)
    hop = config.grid.hop(fs)
    n = len(config.grid.frame_centers(len(s), fs))
    threshold = config.threshold(fs)

    voiced = np.zeros(n, dtype=np.bool_)
    undefined = np.zeros(n, dtype=np.bool_)
    floor_gated = np.zeros(n, dtype=np.bool_)
    floor_rms = 10.0 ** (config.floor_dbfs / 20.0)  # dBFS -> linear RMS amplitude

    for k in range(n):
        start = k * hop
        frame = s[start : start + frame_len]
        # J2 (floor guard) is computed for EVERY frame, independent of J1: a
        # near-silence frame (e.g. +-1 LSB, RMS ~ -92 dBFS) has finite r1, so J1
        # does not fire on it, but it is below the floor -- J2 is what catches
        # the silence J1 structurally cannot. Both-true is coherent (a zero
        # frame is undefined AND below the floor).
        rms = np.sqrt(float(frame @ frame) / len(frame))
        floor_gated[k] = rms < floor_rms

        if start < 1:
            undefined[k] = True  # frame 0: no boundary sample for the lag
            continue
        value = r1(s, start, frame_len)
        if not np.isfinite(value):
            undefined[k] = True  # zero-energy frame: r1 is 0/0
            continue
        # A floor-gated frame is non-voiced regardless of r1: r1 is scale-
        # invariant, so a sub-floor periodic frame could clear the threshold,
        # and the guard must win -- below the floor we do not trust the content.
        voiced[k] = value > threshold and not floor_gated[k]

    return VoicingTrack(
        voiced=voiced,
        undefined=undefined,
        floor_gated=floor_gated,
        fs=signal.fs,
        frame_len=frame_len,
        hop=hop,
    )
