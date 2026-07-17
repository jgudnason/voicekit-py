# r1 — null distribution of the decision-layer lag-1 statistic

This is the analytic provenance for the estimation-noise term of any threshold
placed on `r1` (`voicekit.vuv.decision`), the decision layer's normalized
autocorrelation coefficient at unit sample delay — Atal & Rabiner (1976),
Eq. (3), computed as published. It is the companion to
[vuv8_c1_null.md](vuv8_c1_null.md), which derives the null of the *reproduced
broadcast* `C1` and explicitly does not cover this statistic. The decision to
use `r1` is recorded in [vuv_c1_decision.md](vuv_c1_decision.md); this note is
only the math.

**Ordering statement (honesty first):** the fixture measurements of `r1`
(D2/D3 region means and stds, recorded in the decision doc and VUV11) predate
this derivation. Where this note's results touch those numbers it records
**corroboration, not prediction**. What *is* derive-before-check here: the
synthetic known-value tests landed with `r1` take their expected values from
this note, written first.

## The statistic

For a frame `s[0..N-1]` (`N = VoicingGrid.frame_len(fs)`, 512 @ 16 kHz) with
boundary sample `s0 = s[start-1]` (the sample immediately before the frame),
with `x = (s[0..N-1])` and `y = (s0, s[0..N-2])` its one-sample-delayed
partner:

```
r1 = <x, y> / (‖x‖·‖y‖)
   = ( Σ_{i=1}^{N-1} s[i]·s[i-1] + s[0]·s0 )
     / sqrt( (Σ_{i=0}^{N-1} s[i]²) · (s0² + Σ_{i=0}^{N-2} s[i]²) )
```

This is Atal & Rabiner Eq. (3) term for term: the boundary product enters the
numerator **once** (it is the broadcast of that term N−1 times that makes the
reproduced `C1` a different statistic). Because numerator and denominator are
an exact inner product and its Cauchy–Schwarz bound, **r1 ∈ [−1, +1] always**
— the paper says so in prose ("by definition, varies between −1 and +1",
p. 204).

## White null

Model: `s[0..N-1]` and `s0` i.i.d. zero-mean Gaussian, variance σ² (scale
cancels; set σ = 1).

- **`E[r1] = 0` exactly.** Each numerator term `s[i]s[i-1]` is odd in `s[i]`
  while the denominator is even in every sample, so every
  `E[s[i]s[i-1]·g(even)]` vanishes — the same oddness argument as the
  broadcast note's §1.
- **`Var[numerator] = N` exactly.** N products of two distinct unit normals,
  each variance 1; adjacent products share one sample, but the covariance
  carries the two flanking samples linearly with mean 0, so every off-diagonal
  term is 0 (the broadcast note's `Var[P]` argument, extended by the one
  boundary term — which now contributes variance 1, not (N−1)²).
- **Denominator concentrates:** `‖x‖²`, `‖y‖²` are χ²_N, mean N, relative
  fluctuation O(1/√N); `‖x‖‖y‖ ≈ N`.
- **`Var[r1] ≈ N/N² = 1/N`.** At N = 512: **std ≈ 1/√512 ≈ 0.0442**. This is
  the concentration the broadcast lacks (its boundary term, entering N−1
  times, carried O(1) variance at any N); with the term entering once, its
  share of the numerator variance is 1/N and vanishes.
- **Gaussian limit:** `√N·r1 → N(0, 1)` (Bartlett/Anderson theory of sample
  autocorrelations under white noise; our denominator is the cross-form
  `‖x‖‖y‖` rather than the textbook `Σs²`, and the frame carries the one
  boundary sample — both are O(1/N) perturbations that do not move the
  leading-order law).

So the estimation-noise quantile is the textbook one: **`z(1-α)/√N`**, with a
dimensionless `α` (or z) knob and N from the grid — no fitted constant
anywhere.

## Coloured noise: `E[r1] ≈ ρ`

For stationary noise with lag-1 autocorrelation ρ (and `s0` adjacent to the
frame, hence correlated at the same ρ): every numerator term has expectation
ρσ², so `E[numerator] = Nρσ²`; the denominator still concentrates at Nσ²,
giving

```
E[r1] ≈ ρ        (the broadcast's bias was 2ρ: boundary term double-counted)
```

with spread still O(1/√N) (Bartlett's formula perturbs the variance by
ρ-dependent factors of order one, not its 1/N scale).

Corroboration against the already-measured fixtures (measured first — see the
ordering statement): D3 aspiration `r1` = +0.271 vs broadcast +0.588 ≈ 2×0.271;
D2 frication −0.159 vs broadcast −0.377 ≈ 2×(−0.159); measured noise-region
stds 0.040–0.052, bracketing the white 0.0442 as coloured-noise Bartlett
factors should.

## Threshold form — two terms, deliberately not conflated

The coloured-noise mean shift is a **bias**, not estimation noise: no α makes
`z(α)/√N` clear a ρ that does not shrink with N. The build-order gate
(2026-07-17) therefore ratified the decomposition

```
threshold = ρ_env + z(1-α)/√N
```

where `z(1-α)/√N` is this note's white-null quantile, and **`ρ_env`** is the
operating envelope's noise-colour bound (VUV1 J2: "calibrated for bounded
noise colour, the bound stated") — a *separate term with separate provenance*,
gated independently and **not set here**. The tell that forced the separation:
absorbing the colour into the knob requires z ≈ 6.1 at N = 512, and 6.1/√512 =
0.270 — numerically the measured colour of D3's aspiration. A "significance
level" equal to a fixture's measured noise colour is a fitted constant wearing
a quantile's clothes; the decomposition is what keeps that door shut.

## Degenerate input

A zero-energy frame gives 0/0 = `NaN` (boundedness does not fix zero energy).
The statistic returns it; mapping `NaN` to a label is the decision rule's
finiteness predicate (VUV1 J1), not the statistic's business. A frame at
`start = 0` has no boundary sample; the statistic refuses it (caller error)
rather than silently wrapping to the signal tail.
