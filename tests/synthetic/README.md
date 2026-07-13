# Synthetic V/UV/S fixture (step 7 — VUV)

This directory holds the **define-the-target** oracle for step 7 (voicing
detection). It is deliberately separate from `tests/golden/`: those `.npz`
files are MATLAB captures and are the *parity* oracles for steps 1–6. Step 7
has **no** canonical voicing behaviour to match (the two legacy
implementations were never reconciled and neither is on the captured
pipeline — see the step-7 handoff), so its oracle is a signal whose voiced /
unvoiced / silent structure is *constructed* and therefore exactly known. This
is a synthetic-known-value oracle, not a capture; nothing was captured from
MATLAB to produce it, and it touches none of the golden fixtures or their
tests.

## Files

| File | What it is |
|---|---|
| `make_vuv_fixture.py` | Generator. Deterministic by fixed seed; re-running reproduces the committed bytes. Not run in CI. |
| `vuv_svuvs_16k.wav` | The signal, 16-bit PCM (the committed bytes are the source of truth). |
| `vuv_svuvs_16k.labels.npz` | The two ground-truth channels (below). |
| `vuv_fixture.py` | Loader: returns the signal and both label channels. No reduction, no scoring. |

## The two ground-truth channels — and why the asymmetry matters

The labels are **two independent channels**, and the asymmetry between them is
deliberate:

- **Region table — PRIMARY.** `region_start` / `region_end` (sample indices,
  **start-inclusive, end-exclusive**) and `region_class` (`'S'` / `'U'` /
  `'V'`). The regions partition the whole signal with no gap or overlap. This
  is the oracle: it covers *all* of silence, unvoiced, and voiced, **including
  regions that contain no glottal cycles at all**.

- **Voiced-only GCI list — SECONDARY.** `gci`: the true glottal-closure sample
  positions, known by construction, **inside the V regions only**. One GCI per
  complete synthesized glottal cycle, at the sample of steepest flow-derivative
  closure. It is meaningful to a per-cycle path *if* that framing is later
  chosen — but it is **structurally blind to S and U regions**, because those
  regions have no cycles.

> **Guard against framing sneaking in through scoring.** The region table is
> primary; the GCI list is voiced-only and secondary. Any future scoring that
> reads *only* the GCI list structurally cannot see S or U regions, and would
> therefore silently reintroduce a per-cycle framing that **this gate has not
> chosen**. The framing decision (frame-based track vs per-cycle mask) is
> deferred to the next gate, with this fixture in hand. Scoring must be built
> against the region table as the primary oracle; the GCI list is an optional
> secondary input for a per-cycle path, never the sole ground truth.

The loader reflects this: it returns both channels side by side and performs
**no** frame-center lookup, per-cycle assignment, or label reduction. Those are
scoring concerns, and scoring is not part of this deliverable.

## Fixture standing

This is the **clean-separation baseline oracle**. Its three classes are
energy-separable (V rms ≫ U rms ≫ S floor), so it establishes the **floor, not
the ceiling**: a detector that passes it is not grossly broken on the easy
case. It does **not** validate behaviour on the cases that actually motivate a
multi-feature (Atal-Rabiner) classifier over a naive energy threshold —
low-energy voiced offsets near the unvoiced floor, voiced frication, and
breathy voice where periodicity and noise coexist. A detector can pass this
fixture on energy alone.

The open questions surfaced below — unvoiced spectral realism, voiced-span
tapers, the two-f0 probe — are the **path to a discriminating fixture** that
would exercise those hard cases. They are not cosmetic polish.

## Signal design

Region layout, in order — chosen so every V/UV/S boundary a classifier is
actually tested on appears once:

```
 S  →  V  →  U  →  V  →  S
sil   voiced  unvoiced  voiced  sil
```

covering silence-onset, voiced onset, voiced→unvoiced, unvoiced→voiced, voiced
offset, and offset-to-silence.

Content construction:

- **V** — the existing sustained-vowel synthesis (`make_inputs.synth_vowel`: a
  Rosenberg pulse train through a fixed all-pole vocal tract), reused so voiced
  spans match the steps 1–6 material and the GCIs are known by construction.
  Both V spans use the same f0 (100 Hz); an f0-independence probe with two
  different f0s is a possible *second* fixture (open question below), not
  folded in here.
- **U** — white Gaussian noise: aperiodic, no glottal source, no true GCIs.
- **S** — a low-level Gaussian noise **floor**, not true zero.

Levels are set relative to the voiced RMS (U ≈ 0.30×, S ≈ 0.005×), giving clear
`S ≪ U ≪ V` separation. These are generator parameters, not resolved acoustic
choices.

## Ratified leans applied

- **4a — silence is a low noise floor, not true zero.** True zero would
  reintroduce the log-energy = −∞ / undefined-autocorrelation degeneracies the
  C7 ledger already tracks; that IEEE-edge concern belongs to a *separate*
  degenerate-edge fixture, not this clean V/UV/S test.
- **4b — sharp region boundaries with a documented don't-care guard band.** The
  boundaries in the region table are exact. The guard band (frames/cycles
  straddling a boundary, excluded from scoring) is a **scoring** concern; its
  width couples to the frame length and is deferred to the next gate. This
  signal and its labels apply **no** guard band — the region table stores the
  true sharp boundaries, and a scorer adds the guard band later.

## Open questions surfaced (not resolved here)

- **Sample-rate coverage.** Only a 16 kHz fixture is shipped. One fixture per
  rate (8 k + 16 k) vs one design at both is open; unvoiced spectral content
  and the `fs/400…fs/40` frame-length flag both interact with `fs`. Adding a
  rate is a new `FixtureSpec` plus one line in `main`.
- **Unvoiced synthesis.** White noise is used (exactly known, but spectrally
  unlike real frication). Shaped/filtered noise would exercise the
  zero-crossing / autocorrelation features more honestly. Whether a
  known-answer test needs spectral realism in U is open.
- **Region durations / minimum region length.** Currently 150–200 ms per
  region (each holds several 32 ms/10 ms frames and, in V, ≥20 cycles). The
  minimum classifiable region length is open.
- **Voiced-span realism.** Steady f0/amplitude here; onset/offset tapers or an
  f0 contour are more realistic but complicate the exact V/S boundary.
- **Second f0 fixture** for f0-independence — open whether it is worth a
  separate fixture.

## Firewall for this round

No scoring harness is shipped, sketched, or designed here. Scoring is where the
framing decision gets made in practice (frame-center lookup silently chooses
frame framing; reading the GCI list silently chooses per-cycle), and that
decision is settled at the next gate with this fixture in hand. This fixture is
built to validate **either** framing; the generator, signal, region table,
voiced-only GCI list, and loader are the deliverable, and nothing that consumes
them for scoring is included.
