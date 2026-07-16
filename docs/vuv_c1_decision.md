# VUV C1 — the decision record

This is the decision record for how the step-7 voicing detector relates to the
`C1` feature: what the reference computes, what its source paper specifies, and
what the decision layer will use. It resolves the structural fork opened at the
end of [vuv8_c1_null.md](vuv8_c1_null.md). The two documents deliberately
separate concerns: the null derivation stays tight, mathematical, and checkable
there; the project reasoning lives here. Cross-references: `REFERENCE_NOTES.md`
VUV7 (the reproduced formula), VUV8 (the null and per-frame-unviability
finding), VUV10 (paper-fidelity characterization of the reference).

Primary source, read in full for this record: B. S. Atal and L. R. Rabiner, "A
Pattern Recognition Approach to Voiced-Unvoiced-Silence Classification with
Applications to Speech Recognition," *IEEE Trans. ASSP*, vol. 24, no. 3,
pp. 201–212, June 1976. The reference implementation (`vuvMeasurements.m`,
2004) cites this paper in its header as the definition of its five features.

Three questions have been getting conflated. Separated:

## Q1. What does the MATLAB do? (settled)

The reference `C1` numerator broadcasts the boundary term `s(1)·s0` across the
N−1 lag-1 products (MATLAB vector+scalar addition), so it enters **N−1 times**;
the denominator carries `s0` **once**. Verbatim-confirmed from the source and
reproduced bit-exact against the MATLAB oracle (REFERENCE_NOTES VUV7). Under
an aperiodic frame the statistic is, to 99.8% of its variance, the product of
two boundary samples: a normal-product null, `E[C1] = 0` under white noise,
`std ≈ 1` at **any** frame length — not the textbook `1/√N`. The math is in
[vuv8_c1_null.md](vuv8_c1_null.md); this document does not restate it.

## Q2. What did it intend? (settled from the primary source)

The paper defines (Eq. (3), p. 202), with `s(n), n = 1…N` the frame and
`s(0)` *defined in the text as the last sample of the previous block*:

```
        Σ_{n=1}^{N} s(n)·s(n−1)
C1 = ─────────────────────────────────────
     √( Σ_{n=1}^{N} s²(n) · Σ_{n=0}^{N−1} s²(n) )
```

The boundary term `s(1)·s(0)` enters the numerator **once** — one product among
N — and `s(0)²` enters the denominator once. The paper states the consequence
in prose (p. 204): C1 "by definition, varies between −1 and +1"; its Fig. 4
plots the measured C1 distributions on a [−1, 1] axis.

Against the MATLAB, the comparison is surgical:

- the MATLAB's **denominator** implements Eq. (3)'s denominator term-for-term
  (`sqrt(ssq*([s0; s(1:end-1)]'*[s0; s(1:end-1)]))`);
- the MATLAB's **numerator** differs from Eq. (3) by a single misplaced
  parenthesis: `sum(v + s(1)*s0)` (scalar broadcast, N−1 times) where Eq. (3)
  is `sum(v) + s(1)*s0` (once);
- the MATLAB's header cites the paper as the definition it implements.

**Verdict: the broadcast is a genuine departure from the paper — a
vectorization bug, not a design choice.** And therefore the bounded add-once
form is not "our reconstruction of the author's intent": **it is Atal &
Rabiner's Eq. (3), term for term, computed as published.** A statistic
computing it needs no intent claim at all; it has a citation.

## Q3. Is the measure good enough anyway? (the substantive finding)

No — and the reason is sharper than "lag-1 is a 1976 compromise." The paper's
own training data contains the problem, and the paper's architecture is what
made it survivable.

**The coloured-noise floor is in the paper's Table I.** Lag-1 correlation
conflates "periodic" with "low-pass" *by construction*: any noise with
low-pass colour has positive lag-1 correlation, periodicity or not. The
paper's trained class statistics show exactly this — first-autocorrelation
means (p. 206, Table I):

| class | C1 mean | C1 std |
|---|---|---|
| silence | **0.649** | 0.158 |
| unvoiced | 0.007 | 0.365 |
| voiced | 0.881 | 0.090 |

Their *silence* — soundproof-booth/channel noise, low-pass coloured — reads
**higher** C1 than unvoiced speech, at two-thirds of the voiced mean. The 1976
design never thresholded C1: it ran a five-dimensional Gaussian
minimum-distance rule with full class covariances, **trained per recording
condition** on manually segmented speech (~6 s each from 4 speakers). In that
architecture a high-C1/low-energy silence class is just another trained
centroid; energy and the joint covariance separate it from voiced. Lag-1's
conflation was survivable *because the classifier was trained*.

Our decision rule is a fixed threshold — the trained-model path was rejected
on licensing and generalization grounds (DESIGN §9 item 7; the paper itself
concedes the training "is particular to one set of recording conditions" and
must be redone when they change, which is independent 1976 support for that
rejection). A fixed threshold has **no trained silence class to absorb the
colour**. So D3's measurement did not discover a new limitation; it
rediscovered a constraint the paper's architecture handled and ours
structurally cannot. That — not the statistic's age — is the honest reason
lag-1 needs replacing *in our setting specifically*.

**Re-measured on the fixtures** (2026-07-16, this session, locked grid
N=512/hop 160 @16 kHz; per-frame over windows fully inside each region; dense
slide, stride 8, n=237 per region — the locked grid yields only 12 frames per
region, far too few to estimate the spread of a heavy-tailed two-sample-
dominated statistic):

| statistic | fixture | voiced | non-voiced | gap | per-frame separation |
|---|---|---|---|---|---|
| broadcast C1 | D3 breathy/aspiration | +1.305 ± 1.102 | +0.588 ± 0.964 | 0.72 | 0.3 σ — overlap |
| broadcast C1 | D2 voiced/unvoiced frication | −0.177 ± 1.028 | −0.377 ± 1.025 | 0.20 | 0.1 σ — overlap |
| add-once C1 (Eq. 3) | D3 breathy/aspiration | +0.625 ± 0.017 | +0.271 ± 0.040 | 0.354 | 6.1 σ |
| add-once C1 (Eq. 3) | D2 voiced/unvoiced frication | −0.055 ± 0.052 | −0.159 ± 0.049 | 0.104 | **~1.0 σ** |

Corroborations of the null derivation's `E[C1] ≈ 2ρ` prediction (broadcast
mean ≈ twice the add-once mean, the latter being ρ): D3 aspiration 0.588 vs
2×0.271; D3 voiced 1.305 vs 2×0.625; D2 unvoiced frication −0.377 vs
2×(−0.159) — including the predicted cross-fixture sign flip (D2 high-pass
noise negative, D3 low-pass-ish aspiration positive).

**The measurement's finding is two-sided, and both sides are findings.** The
broadcast statistic is per-frame unviable on *every* fixture (0.1–0.3 σ). The
correct Eq. (3) statistic carries the structural bias — D3's aspiration
measures **+0.271 with no periodicity present at all**, so a white-noise-null
threshold centered at 0 misreads it as voiced — and its separating power is
fixture-dependent: sufficient on D3 (6.1 σ), **insufficient on D2 (~1.0 σ
per-frame)**. The 6 σ figure is D3-only and must not be read as the
statistic's performance; D2 was built to be hard for exactly this family, and
it is — **no lag-1 statistic, correct or not, separates D2 per-frame. `r1`
alone does not solve voicing.**

The paper corroborates the mediocrity from inside: it notes the voiced C1
distribution is "particularly skewed" and suggests "a suitable nonlinear
function of the autocorrelation coefficient, such as the inverse hyperbolic
tangent, would be more appropriate" (p. 206). Lag-1 was adequate to a
trained, five-feature, 10 kHz/10 ms/soundproof-booth setting; it is not the
statistic a modern detector would choose, and its original users already saw
the seams.

## The decision

**The parity obligation attaches to the feature layer, and it is fully
discharged.** Broadcast `C1` stays the golden-mastered feature-layer output:
bit-exact against the MATLAB oracle, unchanged, under its existing name, with
**no flag**. VUV7 stays closed. Nothing about the feature layer moves.

**The decision layer is define-the-target and has no reference to depart
from.** The reference's own decision stages were both rejected at the
architecture gate — C's GMM (non-deterministic) and E's trained centroids
(non-redistributable training corpora) — so there is no canonical decision
behaviour to be faithful to. A from-scratch decision stage computing the
statistic it needs is not "a correction behind a flag being made operative";
it is a new stage in a milestone that never had a reference.

**Therefore the bounded statistic is a separate, named feature of the decision
layer — not a flag on `C1`, not "corrected C1."** Proposed name: **`r1`** —
the normalized autocorrelation coefficient at unit sample delay, per Atal &
Rabiner (1976), Eq. (3), bounded in [−1, 1], concentrating as `1/√N` under an
aperiodic frame. Its docstring describes what it *is* and cites the paper; it
makes **no parity claim** and never touches the golden capture. (`r1` is the
standard autocorrelation-coefficient symbol; a name containing "c1" would
invite exactly the "corrected C1" misreading this decision avoids.) The
reproduce-and-quarantine discipline is not inverted, because nothing
reproduced is being corrected: `C1` keeps its name, its capture, and its
parity gate.

This decision rests on Q1 and Q2 — the reproduced statistic is structurally
unfit per-frame and the bounded form is the published one — **not on `r1`'s
fixture performance**. Q3 cuts both ways and is inherited openly: `r1`
separates D3 (6.1 σ) and fails D2 (~1.0 σ); `r1` alone does not solve
voicing, and the classifier gate takes that as an input fact, not a
disappointment to be tuned away.

**The counter-argument, stated fairly.** This *looks* like making a correction
operative while relegating the reproduction to a relic — which would invert
the V3 pattern, where the knowable uncrossing of `h1h2`/`hrf` is documented
but deliberately **not** applied, golden parity being the gate. If V3's
discipline means "a known correction stays dormant until corpus evidence
flips it," then a shipping classifier consuming `r1` while ignoring `C1` is
functionally the correction gone live, whatever the field is named. The
reading this record adopts instead: V3 governs the *feature layer*, where a
golden capture exists and the correction would change golden-mastered values
under the same name — there, reproduce-and-quarantine binds. The decision
layer has no capture, no reference behaviour, and no parity gate to protect;
choosing its input statistic is design, not correction. The distinction is
real but a reader should see both readings and judge — it was put to the
rule's author as a rule-reading question, and this decision records the
answer, not a unilateral reinterpretation.

**Why the reproduced `C1` cannot serve in the decision layer** (the measured
structural fact, not a threshold preference): its per-frame null does not
concentrate with N — the O(1) spread is a single boundary product, so no
threshold placement helps ([vuv8_c1_null.md](vuv8_c1_null.md) §5). Smoothing
it to usefulness needs, by the two-sided requirement
`w > (z·(σ_V+σ_N)/gap)²` on the re-measured D3 numbers above, **w ≈ 33 frames
(330 ms) at z=2 and w ≈ 75 frames (750 ms) at z=3** — 16–36× the grid's guard
band W (336 samples = 21 ms), longer at z=3 than D1's *entire* 370 ms
voiced→offset→tail structure, and longer at either z than the 220 ms
decay+tail region D1 exists to discriminate. A smoothing window that erases
the transition it is meant to detect is structurally unfit, independent of
where the threshold sits. The reference's own `medfilt1` remedy does not
transfer — see below.

No threshold value is set here. The `r1` threshold's provenance remains as
ratified (VUV1): derived from the analytic null (`1/√N` — the *textbook* null
is correct for `r1`, which is exactly what makes it usable per-frame) with a
dimensionless significance knob, subject to the coloured-noise constraint
below, and never fitted to D1/D2/D3. Implementation of `r1` and the decision
rule belongs to the decision-rule gate that follows this record.

## Further research

**Pitch-lag correlation instead of lag-1.** The project already knows lag-1 is
the wrong lag: the D2/D3 fixture assertions were moved from lag-1 to the pitch
lag precisely because lag-1 cannot distinguish genuine F0 periodicity from
tilt-induced smoothness. Re-measured (region-level, this session): at D3's
pitch lag (89 samples @ 180 Hz), breathy voiced reads **+0.482** against
aspiration **+0.013** — the coloured floor all but vanishes, because noise
colour concentrates at short lags and the 300–6000 Hz aspiration has
decorrelated by lag 89. Compare lag-1's +0.625 vs +0.271: the pitch lag
trades a small drop in the voiced reading for a ~20× drop in the noise floor.
(D2 stays hard everywhere: +0.068 vs −0.020 at its pitch lag — sign-correct
but small; the VFR ≈ 0 dB regime is genuinely marginal for any correlation
feature.) The real obstacle is structural: a pitch-lag correlation needs an F0
estimate, and F0 estimation conventionally needs a voicing decision — a
circularity. Step 9's YIN is on the roadmap; whether voicing gates F0, F0
gates voicing, or the two co-estimate is a genuine open research question,
not a TODO.

**The lag-band generalization.** Already forward-noted in VUV4 against the
jitter hardening knob: once cycle jitter spreads the pitch peak across a band
of lags, a fixed-bin pitch-lag statistic must widen to a lag-band search
(max correlation over `fs/f0_max … fs/f0_min`). Same machinery; the fixture
assertion widens the same way when the jitter knob turns.

**Why the reference's own remedy doesn't transfer.** The reference's decision
stage applied `medfilt1` to C1 — evidence its author knew per-frame C1 was
noisy. The null derivation now explains *why* (two-sample boundary
domination) and quantifies why the same remedy cannot rescue our case: the
required window (330–750 ms, above) is 16–36× our guard band and longer than
D1's discriminating structure. Smoothing a statistic whose noise does not
concentrate is paying time resolution for variance reduction at a rate fixed
by the O(1) spread; the reference could afford it (its consumers had no D1),
we cannot. The 1976 paper also smoothed — a nonlinear smoothing of the
3-level decision contour using per-class probability measures (Eq. 11) — but
as post-processing of a trained rule's output, not as the thing that makes a
threshold viable at all.

**The coloured-noise floor is a family property.** Any correlation-family
feature carries `E[stat] ≈ ρ_noise(lag)` on aperiodic input — it is a
property of correlation statistics, not of one implementation, and it does
not vanish by fixing the broadcast (add-once D3 aspiration: +0.271) or by
changing lag (it shrinks at the pitch lag only because typical noise colour
decays with lag — a low-frequency rumble under a low-pitched voice would
restore it). Table I is the 1976 evidence: silence at C1 = 0.649 is the same
floor, seen by the paper's own trained means. Any future alternative from
this family must be chosen with the floor priced in, not in the expectation
that it disappears. For the fixed-threshold rule this binds concretely: the
threshold must clear the *local noise colour*, not the white null's zero.

**Distribution shape.** The paper's inverse-tanh remark points at a real
refinement: `r1` near ±1 is variance-compressed (the voiced distribution is
skewed), and a Fisher-z / `atanh` transform is the classical stabilizer. If a
future rule wants a symmetric statistic for its null, `atanh(r1)` is the
first candidate — noted, not designed.

**What the classifier gate inherits.** (i) **`r1` alone does not solve
voicing.** D2 is not separated per-frame by any lag-1 statistic, correct or
not (~1.0 σ); whether the other four features, aggregation, or a pitch-lag
statistic carries D2 is open — VUV3's scope boundary (sufficiency-elimination
only, no necessity claims) applies unchanged. (ii) The silence pre-gate
question (VUV1) is untouched by this record, including its separately-named
threshold-provenance requirement.
