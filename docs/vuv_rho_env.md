# ρ_env — the colour margin: a declaration, with Table I as its constraint

This is the provenance record for `ρ_env`, the colour-margin term of
`threshold = ρ_env + z(1−α)/√N` ([vuv_r1_null.md](vuv_r1_null.md)).

**What this is, and is not.** The ρ_env gate (2026-07-17) first sought a
*derivation* from Atal & Rabiner's Table I — the same statistic, real speech,
measured, published 1976, under the conditioned-input chain VUV12 ratified
(Table I was measured *post*-Eq. (1)-HPF), predating our fixtures by five
decades. **That derivation did not land**, for a structural reason recorded
below: Table I reports class *moments*, not phones, and its unvoiced class
bundles the material VUV13 already excludes — so it constrains ρ_env to a
range and cannot pin a point within it. What follows is therefore a
**declaration** (the gate's option (ii)) with Table I as its supporting
constraint, its scope stated, and the fixtures used only to *check* it
afterward in their ratified out-of-sample role.

**And the declaration declares a range, not a value.** A first attempt pinned
the point; review established that the pin was selected with its fixture
outcome already visible, and it did not survive. The range, the straddle it
leaves, and the process finding behind the retraction are recorded below —
the retraction being the more useful artifact.

## Source data and ρ_env's role

ρ_env's ratified role (VUV1 J2, build-order gate): an upper bound on the
*mean* `r1` of in-envelope aperiodic noise — a property of the noise the
detector is calibrated for, not a decision compromise. Table I (10 kHz,
N = 100 blocks, post-HPF; first-autocorrelation column):

| class | mean | std (total) |
|---|---|---|
| silence | 0.649 | 0.158 |
| unvoiced | 0.007 | 0.365 |
| voiced | 0.881 | 0.090 |

**Estimation-noise decomposition.** Table I's stds mix per-frame estimation
noise at their N = 100 with genuine colour spread across frames. Removing the
estimation part in quadrature (white-null 1/√100 = 0.100 for the unvoiced
class; Bartlett `√((1−ρ²)/N)` elsewhere): unvoiced colour spread
√(0.365² − 0.100²) = **0.351**; voiced **0.077**; silence **0.139**. The
corrections are small — the classes' overlap is colour, not measurement.

## Why the derivation could not pin a point (the finding)

The natural full-class constructions — coverage at k = 2 (0.007 + 2·0.351 =
0.709) and U/V equal-error (0.724) — both sit at ≈ 0.71–0.72 at 10 kHz, and
**both are wrong for this detector**, because Table I's unvoiced class
*bundles the VUV13-excluded material*: its upper tail (+2σ ≈ 0.71) is
precisely the voiceless-vowel aspiration whose exclusion from the fixed-lag-1
guarantee is already a ledgered limit. A margin built to cover that tail
**double-counts an already-excluded limit into the threshold**, driving it into
the region where hard-case voiced speech lives. Table I cannot decompose its
own class for us — it reports moments, not a per-phone breakdown. Hence: a
range, not a point; hence a declaration, not a derivation.

## The declaration — rule fixed first, in this order

**Ordering discipline.** The value was not chosen; the rule was, and the value
fell out. The steps below were taken in the order written, and the record
shows the grounds of each before the number it implies.

### Step 1 — the conversion model: exponential

`r1` compares adjacent samples: lag τ = 1/fs. At 16 kHz the lag (62.5 µs) is
shorter than Table I's (100 µs), so for the same spectrum the correlation is
**higher**: ρ(16k) ≥ ρ(10k). The quantitative map needs a spectral-shape
model. **Chosen: exponential correlation**, ρ(τ) = e^(−τ/τc), giving
`ρ₁₆ = ρ₁₀^(10/16)`. Grounds (from Klatt and linear systems; **no fixture is
referenced, and the argument is checkable independently**):

1. Klatt (1980, p. 7) specifies the turbulence/aspiration source as a
   pseudo-random generator through a **−6 dB/octave low-pass**. White noise
   through a first-order low-pass *is* a first-order Markov (Ornstein–
   Uhlenbeck) process, whose autocorrelation is **exactly** exponential — not
   an approximation, but the exact ACF of the stated source model.
2. Exponential ACF ⟺ Lorentzian spectrum ⟺ −6 dB/octave roll-off: Klatt's
   number is this model's spectral signature.
3. The **quadratic** alternative (1−ρ₁₆ = (10/16)²(1−ρ₁₀)) requires a finite
   second spectral moment `∫ω²S(ω)dω`, i.e. roll-off steeper than −9 dB/oct.
   At −6 dB/oct that integral diverges and the ACF has a **cusp** at τ = 0 —
   the exponential's signature, not the parabola's.
4. Post-source shaping pushes the same way: radiation adds +6 dB/oct
   (flattening the source — *more* HF content, second moment even less
   convergent); formants add resonance, not steep global roll-off. Only the
   anti-alias/recording band-limit restores fast roll-off, and that governs
   only at lags far shorter than 62.5 µs. **The quadratic is the τ→0 asymptote
   of a band-limited recording; the exponential is the finite-lag model at the
   lag actually probed.**

*Known gap in this conversion:* it models the **lag** change and not the
**bandwidth** change, and the two push opposite ways — see caveat (b) below.

*Assumption check (gate condition 1):* the assumption is a smooth, decreasing,
cusp-at-zero ACF from a −6 dB/oct-shaped source. **Our fixtures did not supply
it** — their noises are band-limited *white* constructions (sinc-family,
oscillatory ACF), a different family entirely. The models' divergence at mid-ρ
(at ρ₁₀ = 0.36: 0.53 exponential vs 0.75 quadratic) is why the model must be
named and committed rather than left open: it is the loosest joint in the
chain, and the declaration carries its model's name.

### Step 2 — the construction: the ground admits a range, and cannot pin k

The double-counting finding excludes the full-class constructions, so the
margin must cover the unvoiced class's **bulk** rather than its
VUV13-occupied tail. **That ground bounds k from above and not from below**,
and it cannot locate the tail's start — Table I reports moments, not phones,
which is the same limitation that sank the derivation. Conventional bulk
choices span k ∈ [1, 2]:

| k | ρ_env(10k) | ρ_env(16k) | threshold (z=2) | D3 breathy (0.625) |
|---|---|---|---|---|
| 1.00 | 0.358 | **0.526** | 0.615 | survives by 0.010 |
| 1.25 | 0.446 | 0.604 | 0.692 | excluded |
| 1.50 | 0.534 | 0.675 | 0.764 | excluded |
| 2.00 | 0.709 | 0.807 | 0.895 | excluded (double-counts VUV13) |

**The admitted range is ρ_env(16k) ∈ [0.53, 0.81], and it straddles the
breathy case.** The rows above compare ρ_env against breathy's region *mean*
(0.625); on that reading breathy survives only for **k < 1.032**, the very
floor of the range. **The fixtures cannot adjudicate within the range:** using
D3 to choose k is precisely the forbidden fit, and it is the only instrument
that would discriminate. So the declaration **declares a range and cannot pin
the point** — which is the honest terminus of this evidence.

**Correction (measured 2026-07-18, at the classifier assembly — the mean
reading was too loose).** Breathy is not one value but a per-frame
distribution: running `detect_voicing` over the region, its `r1` spans
**[0.593, 0.661]**, mean 0.625. So even at the range's floor (ρ_env = 0.53,
threshold 0.6027 at α = 0.05) the threshold already cuts breathy's lower tail
— **0.83 of the region reads voiced there, never all of it** — and at the
midpoint (0.67) none of it does. Full detection of the region would need
ρ_env ≤ **0.520**, *outside the declared [0.53, 0.81] range entirely*. The
user-facing statement is therefore stronger than "straddled": **no admissible
envelope detects breathy voice at HNR ≈ 0 completely** (ledgered as VUV17).
**This does not move the range.** The range is declared-not-derived and
Track-B-adjudicated; a measurement that makes a limit *worse* is no more a
licence to move a parameter than one that makes it better (the symmetric
guard to caveat (a)'s). It sharpens what the straddle costs, nothing more.

### The process finding (why the range is declared and not a point)

An earlier draft of this document pinned k = 1 and reported that breathy
"passes by 0.010." **That pinning did not survive review, and the reason is
recorded here rather than quietly corrected**, because it is the more useful
artifact:

- **Sequence, plainly:** k = 1 was **not** fixed before its value was
  computed. It entered the record already paired with its D3 comparison, and
  it entered *after* k = 2 had been computed and seen to fail D3. The
  double-counting ground was reasoned first and is genuine — but it justifies
  "cover less than the full class," not k = 1 specifically. k was selected
  from the range the ground admits, with the landing visible.
- **The tell:** k = 1 sits at **97% of the survival boundary** (k < 1.032).
  Landing within 3% of the only edge where D3 survives, while blind to D3, is
  not a coincidence a reader should be asked to accept.
- **The shape is familiar, one level up.** This is the same failure as the
  z ≈ 6.1 tell that motivated the `ρ_env + z/√N` decomposition in the first
  place (a "significance level" coming out numerically equal to D3's measured
  aspiration colour — [vuv_r1_null.md](vuv_r1_null.md)). The decomposition
  **moved** the free parameter from α to k; it did not remove it. A fit will
  find whatever freedom the structure leaves, which is an argument for
  declaring ranges wherever the evidence only supports a range.

**Consequence, stated:** whether breathy voice at HNR ≈ 0 falls inside the
operating envelope is **a declaration choice, not an evidence-determined
fact**. Table I plus the VUV13 exclusion do not settle it; only Track B can.

### Step 3 — the out-of-sample check, as it landed

Fixture values (measured before this work — corroboration framing, per the
ordering discipline), against the admitted range rather than a pinned point:

- **D3 aspiration (0.271): correctly excluded across the entire range**, at
  every α — a real (if weak) check the range passes, and consistent with
  VUV13's physics for the *mild* instance D3 constructs. Real strong
  aspiration is not covered at any α (VUV13).
- **D3 breathy (per-frame [0.593, 0.661], mean 0.625): straddled, and never
  fully inside.** Even at the range's floor the threshold cuts its lower tail
  (0.83 of the region voiced, measured; see the correction above), and it is
  excluded outright by the midpoint. Not a pass, not a fail: **undetermined by
  this evidence, and incompletely detected under every admissible ρ_env.**
- **D1/D2:** unaffected by ρ_env's location within the range (D1's regions are
  separated by the pre-gate/energy structure, not the colour margin; D2's
  voiced fricative at −0.055 is below the entire range and is a stated limit —
  VUV11).

*Chain caveat:* these fixture values are **unconditioned**, while the margin
they are checked against derives from Table I's **post-Eq. (1)** measurements.
The comparison is not chain-matched — see caveat (a) below.

**What ships is therefore the range, not a number.** `ρ_env` belongs in
`VuvConfig` as an **explicit, documented parameter** whose default must be
named as the convention it is, with this range and this straddle documented
next to it, so a caller can see exactly what the choice costs and Track B can
adjudicate it. Recommended, not decided here: the classifier gate takes it.

## Caveats surfaced at the conditioning gate (2026-07-17)

Both were found while surfacing VUV12's conditioning helper — by reading the
paper's front end against the ratified precondition — after this declaration
was committed. **Neither moves the declared range**, and neither is a reason to
revisit it: the range is declared-not-derived and Track-B-adjudicated, so these
are caveats on its *accuracy*, recorded where the range is stated.

### (a) The conditioned-chain gap: Table I is post-Eq. (1); the precondition does not require conditioning

Table I was measured **after** the paper's Eq. (1) 200 Hz high-pass (its Fig. 1
order is scale → HPF → block → measurements). VUV12's ratified precondition is
weaker: *input DC-free and free of sub-speech-band energy* — which does **not**
require Eq. (1), and which our fixtures **already satisfy** unconditioned (they
are zero-mean synthetic with no sub-speech-band content). Two consequences:

- **VUV11's and VUV13's fixture measurements stand, unmoved.** They are
  measurements of precondition-compliant signals; no conditioning is owed on
  them, so nothing about D2's ~1.0 σ or D3's numbers changes.
- **But Step 3 above compared a conditioned-chain margin against unconditioned
  fixture values.** Eq. (1) attenuates our fixtures' fundamentals materially —
  computed from the paper's coefficients: **D1 (120 Hz) −11.5 dB, D2 (150 Hz)
  −7.5 dB, D3 (180 Hz) −4.4 dB** (the filter attenuates a low fundamental
  rather than annihilating it — VUV12 — but 4–12 dB is not nothing). Since
  `r1`'s voiced value is driven by low-frequency energy concentration,
  conditioning would move the fixtures' `r1` **downward**, and Step 3's
  comparison is therefore not chain-matched.

**Measured 2026-07-17 (the helper now exists) — and (a) is DISCHARGED.**
`condition()` applied to D1/D2/D3, `r1` re-measured on the same regions, with
predictions written before measuring:

| region | measured Δr1 |
|---|---|
| D1 `voiced_steady` / `voiced_decay` / `subfloor_residual` | −0.0016 / +0.0008 / +0.0005 |
| D1 `floor_lead` / `floor_trail` (white noise) | −0.0125 / −0.0117 |
| D2 `voiced_modal` / `voiced_fricative` / `unvoiced_fricative` | −0.0015 / **+0.0020** / +0.0012 |
| D3 `modal_voiced` / **`breathy_voiced`** / `aspiration` | −0.0010 / **+0.0094** / +0.0134 |

- **Every delta is small** — max |Δ| = 0.0134, an order below the 0.095 gap
  between breathy (0.625) and this range's floor (0.53). The conditioned-chain
  gap is **real in principle and negligible in practice**.
- **D3's breathy moved *up*** (0.625 → 0.634): *away* from the range's floor and
  from the z=2 threshold, not toward it. The chain-matched comparison is
  marginally *more* favourable than Step 3's, so the gap narrows and this caveat
  weakens rather than bites.
- **The range does not move, and nothing here argues it should.** The guard
  binds regardless of which way the measurement fell — it ran as a check, not as
  an input. Track B adjudicates.

*A finding about the prediction, recorded because it was wrong.* Both regions
with real content (D2 `voiced_fricative`, D3 `breathy_voiced`) were predicted at
**−0.045** and measured **+0.002 / +0.009** — wrong sign. Cause, established:
the first-order model treated Eq. (1) as "attenuate the fundamental, unity
elsewhere", but the filter carries a **~0.6 dB low-frequency emphasis across the
whole passband** (+0.43 dB at 500 Hz → −0.18 dB at 4 kHz) acting on *all* the
energy — which alone predicts +0.0118 of `aspiration`'s +0.0134, a region with
no fundamental at all — and the fundamental's energy share was overestimated
~2× (measured `w` = 7.7% for breathy; the F1 resonance dominates the budget).
Even corrected, the two-term model gives −0.0067 vs +0.0094: **the first-order
model is inadequate.** The exact computation — apply `|H|²` to each region's own
measured spectrum — reproduces all four deltas to within 0.0005. For a gently
tilted filter the passband term is not a correction to the stopband term; it
dominates.

### (b) The unmodeled bandwidth term in the fs conversion

The paper's chain is **4 kHz LPF → 10 kHz sampling → 200 Hz HPF**, so Table I is
measured on **4 kHz-band** speech; our 16 kHz signals carry **0–8 kHz**. Step 1's
conversion modeled the **lag** change (shorter lag → **higher** ρ) but not the
**bandwidth** change (more high-frequency content → **lower** ρ). **The two
partially cancel**, so the declared range **0.53–0.81 may be biased high** by an
unquantified amount.

The 4 kHz LPF is **not ours to reproduce**: it was an anti-alias filter for
10 kHz sampling, our input arrives band-limited by its own recording chain, and
VUV12's ratified scope is the 0 Hz end (J3), not the Nyquist end. So this is a
gap in the *transfer*, not a missing stage in the *helper*. It joins conditions
1–3 as a stated limit on how precisely 1976 numbers can speak to a 16 kHz
detector — which is what Track B adjudicates.

**Linked provenance (recorded here because the coupling is easy to miss):** the
conditioning helper's cutoff is a config parameter with the paper's values as
its default. **Changing it leaves the paper's provenance *and* ρ_env's Table-I
provenance together** — Table I's numbers describe speech conditioned by Eq. (1)
specifically, so a different corner puts the input outside the chain this
declaration's supporting constraint was measured on.

## Gate condition 2 — the accepted error rates, stated

Table I's own 2σ overlap is the honest bound: unvoiced +2σ (colour) ≈ 0.71
sits essentially *at* voiced −2σ ≈ 0.73. Any 1-D margin therefore has finite
error **by the source's own measurement** — the full-class constructions
accept ~2% false-voiced and ~2% false-non-voiced at 10 kHz *before* the hard
cases. Across the admitted range the accepted false-voiced rate on Table I's
unvoiced class spans ~16% (k = 1) to ~2% (k = 2) nominal — that tail being
VUV13's separately-ledgered material, which is why covering it double-counts.
Every point in the range accepts errors on *both* sides; this is why the 1976
system classified in five dimensions. **No statement here implies a clean 1-D
separation exists.**

## Gate condition 3 — corpus narrowness, stated

Table I is four speakers (2 male, 2 female), ~6 s each, one soundproof booth,
one microphone/tape chain, read speech; the paper itself notes the Gaussian
fit is imperfect for voiced C1 (skewed) and that its training "is particular
to one set of recording conditions." Table I is citable and out-of-sample; it
is **not universal**. Any margin built on it inherits that scope, and the
declaration is validated at Track B or not at all.

## What ships, and what this establishes

The declaration is the operating envelope VUV1 J2 requires, in the only form
this evidence supports: **stated** (this document — model named on Klatt
grounds, the admitted range and its straddle named, error rates and scope
stated, the process finding recorded), **checked** out-of-sample (Step 3, as
it landed: aspiration excluded across the range; breathy undetermined),
**stratified** in scoring (VUV5/VUV11/VUV13), **validated at Track B** or
revised there. Fixed-threshold `r1` with this stated envelope remains the
ratified architecture; what is *not* ratified is any point within the range.

It also establishes the third of three independent forcing functions for the
successor statistic — see **VUV14**: Table I's measured 1-D overlap says a
fixed lag-1 margin carries ~2% error each side on 1976's *easy* material
before any hard case, and the evidence cannot even determine whether a
by-construction-voiced region (D3's breathy at HNR ≈ 0) is inside the
envelope.
