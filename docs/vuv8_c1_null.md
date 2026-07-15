# VUV8 — analytic null distribution of the reference C1 statistic

This is the analytic provenance for any threshold placed on the reference `C1`
voicing feature (`voicekit.vuv.features`). It exists because the reference `C1`
is **not** the textbook lag-1 autocorrelation, so the textbook `1/√N` null does
not apply and there is no reference derivation to reproduce — it must be
established mathematically. This note is self-contained and checkable.

Cross-references: `REFERENCE_NOTES.md` VUV7 (the reproduced C1 formula and its
broadcast quirk, confirmed bit-exact against MATLAB) and VUV8 (the blocking
status this note discharges, and the per-frame-unviability finding).

## The statistic

For a frame `s[0..N-1]` (length `N = VoicingGrid.frame_len(fs) = 512` at 16 kHz)
with boundary sample `s0 = s[start-1]` (the sample immediately before the frame),
the reference computes (reproduced verbatim, commit `2c93bff`):

```
P   = Σ_{i=1}^{N-1} s[i]·s[i-1]        # lag-1 product sum, N-1 terms
B   = (N-1)·s[0]·s0                     # boundary term, broadcast N-1 times
num = P + B
ssq = Σ_{i=0}^{N-1} s[i]²              # frame energy, N terms
V   = s0² + Σ_{i=0}^{N-2} s[i]²        # energy of [s0, s[:-1]] -- NOT the ssq vector
C1  = (P + B) / sqrt(ssq · V)
```

Two structural facts, both established from the MATLAB source:
- the numerator boundary term `s[0]·s0` is a **scalar broadcast** across the N-1
  products (MATLAB vector+scalar), so it enters **N-1 times**;
- the denominator's `s0` enters **once**, as one element of `[s0, s[:-1]]`, a
  vector different from the one `ssq` sums.

That numerator-broadcast / denominator-once asymmetry breaks Cauchy-Schwarz and
is why `C1` is unbounded above (1.448 measured on D3).

## Model

Aperiodic frame: `s[0..N-1]` i.i.d. zero-mean Gaussian variance σ²; `s0` from the
same law and, **under the white model, independent** of the frame. `C1` is
scale-invariant, so set σ = 1.

- *Buys:* tractable moments and a clean leading-order law.
- *Costs:* real aperiodic noise is coloured (`s0` is *adjacent* to `s[0]`, hence
  correlated). That is the real limit — see "Coloured noise" below.

## 1. Moments of the null

**`Var[P] = N-1`, complete (all pairs).** With `T_i = s[i]s[i-1]`,
`Var[P] = Σ_i Var[T_i] + 2 Σ_{i<j} Cov[T_i,T_j]`.
- Diagonal: `Var[T_i] = E[s[i]²]E[s[i-1]²] - 0 = 1`; summed, `N-1`.
- Off-diagonal, exhaustively: **disjoint** pairs (`j ≥ i+2`) are independent, so
  `Cov = 0`; **adjacent** pairs (`j = i+1`) share `s[i]`, but
  `Cov[s[i]s[i-1], s[i+1]s[i]] = E[s[i]²]·E[s[i-1]]·E[s[i+1]] = 1·0·0 = 0` — the
  shared sample enters squared, the flanking samples linearly with mean 0.
- Every off-diagonal term is 0, so `Var[P] = N-1` exactly.

**`Var[B] = (N-1)²`.** `s[0]·s0` is a product of two independent standard
normals: mean 0, variance 1. So `Var[B] = (N-1)²·1`.

**`Cov[P,B] = 0`** (every term carries `E[s0] = 0`). Hence
`Var[num] = (N-1) + (N-1)² = (N-1)·N`.

**Denominator concentrates.** `ssq, V ~ χ²_N`, mean `N`, relative fluctuation
`O(1/√N)`; `sqrt(ssq·V) ≈ N·(1 + O(1/√N))`.

**`E[C1] = 0` exactly.** By `s0 → -s0` symmetry the `B` contribution averages to
0, leaving `E[P/sqrt(ssq·V)]`; each `E[s[i]s[i-1]·g]` with `g` even in every
sample vanishes by oddness.

**`Var[C1] ≈ (N-1)/N`.** Leading order: `Var[num]/N² = (N-1)N/N² = (N-1)/N`.
**At N=512: Var ≈ 0.998, std ≈ 0.999 ≈ 1** — larger than the textbook `1/√N ≈
0.044` by a factor `√N ≈ 22.6`, and essentially **N-independent**.

## 2. The broadcast dominates -> the null is a product-of-two-Gaussians

`std[B] = N-1 ≈ 511` vs `std[P] = √(N-1) ≈ 22.6`: `B` dominates by `√N ≈ 22.6`,
carrying `(N-1)/N ≈ 99.8%` of the numerator variance. So, dividing by `≈ N`:

```
C1 ≈ (N-1)/N · s[0]·s0  +  P/N  ≈  s[0]·s0  +  (1/√N)·(zero-mean frame correlation)
```

**Headline:** under the null the reference `C1` is, to 99.8% of its variance, the
**product of two boundary samples `s[0]·s0`** — a **normal-product** variable,
density `f(z) = (1/π)·K_0(|z|)` (modified Bessel; mean 0, variance 1, excess
kurtosis 6, tails ~ `e^{-|z|}`) — **not a correlation statistic**. The frame's
actual lag-1 correlation content (the `P` term) survives only as a `1/√N ≈ 0.044`
correction. The broadcast bug didn't just make `C1` unbounded; it made the null
depend on **2 of the 512 samples**.

## 3. Threshold form

Voicing ⇒ high `C1`, so a one-sided upper quantile:
**`threshold = f(α, N) ≈ Q_NP(1-α)`**, the `(1-α)` quantile of the normal-product
`K_0/π`, numerically evaluated (not a closed form, not a fitted constant), with
only a weak `O(1/√N)` N-dependence from the `P/N` smoothing. The `VuvConfig` knob
stays a dimensionless α; the concrete threshold is `Q_NP(1-α)·(N-1)/N`.

## 4. Falsifiable prediction (written before any measurement)

White i.i.d. frame, N=512:
- `E[C1] = 0`; `std[C1] ≈ 0.999`.
- Distribution: normal-product (`K_0/π`), heavy-tailed, **not** Gaussian, **not**
  `1/√N`-concentrated.
- Approx one-sided quantiles (leading-order tail `f(z) ≈ (2πz)^{-1/2}e^{-z}`, to
  be pinned numerically from `K_0`): `Q_NP(0.95) ≈ 1.6–1.8`, `Q_NP(0.99) ≈
  2.8–3.2` (vs Gaussian 1.645 / 2.326).
- **Stakes:** a textbook-null threshold would sit at `≈ 1.645/√512 ≈ 0.073`; the
  correct null puts it at `≈ 1.7` — a factor **~23**. The wrong threshold passes
  essentially every noise frame as voiced. This is why VUV8 was blocking.

Coloured fixture noise (below): `E[C1] ≈ 2ρ` — negative for D2 (high-frequency
band-pass, ρ<0), sign-of-ρ for D3/floor; std still O(1). Voiced-side corroboration
(already-measured, does not touch the null): `2ρ_v ≈ 2·0.72 ≈ 1.44` vs the 1.448
measured on D3 in commit 3b.

**Check (a separate step, not done here):** measure `C1` on the fixtures' noise
regions and confirm `mean ≈ 2ρ_noise`, `std ~ 1`, non-concentrating. A mismatch is
a finding about the derivation or the noise model — never a licence to adopt the
measured value.

## 5. Coloured noise, and per-frame unviability

Real aperiodic noise (D2 band-passed frication, D3 tract-shaped aspiration) is
**coloured**, and `s0` is **adjacent** to `s[0]`, so both correlate at the noise
lag-1 coefficient ρ. Then `E[s[0]s0] = ρ` and `E[P]/N ≈ ρ`, giving

```
E[C1] ≈ 2ρ     (white ρ=0 recovers E[C1]=0)
```

- **The white null is biased by `2ρ`.** For positively-correlated (low-pass-ish)
  noise `ρ>0`: non-voiced frames sit above the white-null mean, so the white-null
  threshold is **optimistic (too low) -> false positives**. For high-pass noise
  (D2, ρ<0) it shifts negative -> conservative. Optimism depends on the **sign of
  the local noise colour**; it cannot be assumed safe.

- **Per-frame unviability (a finding, not a caveat).** The null's O(1) spread
  comes from a **single boundary product** `s[0]·s0`, not an average, so it
  **does not concentrate with N**: `std ≈ 1` at any frame length. Voiced sits at
  `2ρ_v ≈ 1.4`; voiced and the non-voiced tail overlap heavily frame-by-frame. No
  threshold fixes this — it is a property of the statistic, not of where the
  threshold sits. **Independent corroboration:** the reference's own decision
  stage applied `medfilt1` to smooth C1 — the reference knew and smoothed.

## The decision-rule gate's opening question (not a threshold question)

Because per-frame C1 does not concentrate, the decision-rule gate opens on a
**structural** fork, which must **not** be absorbed into a threshold choice:

1. **Smooth `C1` across frames** (what the reference did with `medfilt1`). Keeps
   the reproduced, golden-mastered formula, but the decision stops being
   per-frame, and the smoothing window needs its **own out-of-sample provenance**
   — it cannot be fitted to D1/D2/D3 any more than the threshold can.
2. **Use the add-once C1** (bounded, a proper normalized cross-correlation that
   concentrates as `1/√N`, making a per-frame threshold viable). But this
   **corrects a reproduced reference quirk**, diverging from the just-golden-
   mastered feature layer, so it needs a **named quarantine flag and its own
   ledger entry**, per the project's reproduce-and-quarantine rule.

This fork is the decision-rule gate's first question; the threshold value is
downstream of it and still blocked until it (and the fixture check of item 4's
prediction) are settled.
