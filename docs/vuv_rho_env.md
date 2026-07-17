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
breathy case.** Breathy voice at HNR ≈ 0 survives only for **k < 1.032** — the
very floor of the range. **The fixtures cannot adjudicate within it:** using
D3 to choose k is precisely the forbidden fit, and it is the only instrument
that would discriminate. So the declaration **declares a range and cannot pin
the point** — which is the honest terminus of this evidence.

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
- **D3 breathy (0.625): straddled** — inside the envelope only at the range's
  floor (k ≲ 1.03), where its margin (0.010 at z = 2) is in any case well
  inside the threshold's own estimation noise (0.044), and excluded outright
  above it. Not a pass, not a fail: **undetermined by this evidence.**
- **D1/D2:** unaffected by ρ_env's location within the range (D1's regions are
  separated by the pre-gate/energy structure, not the colour margin; D2's
  voiced fricative at −0.055 is below the entire range and is a stated limit —
  VUV11).

**What ships is therefore the range, not a number.** `ρ_env` belongs in
`VuvConfig` as an **explicit, documented parameter** whose default must be
named as the convention it is, with this range and this straddle documented
next to it, so a caller can see exactly what the choice costs and Track B can
adjudicate it. Recommended, not decided here: the classifier gate takes it.

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
