# voicekit-py — Step 7 (VUV) handoff

## What this project is

voicekit-py is a from-scratch, Apache-2.0-licensed Python reimplementation of a long
line of MATLAB voice-analysis research code — the DYPSA/YAGA GCI-GOI detector, IAIF,
and per-cycle voice-source feature extraction. It is **clean-room**: the domain
algorithms are implemented from published descriptions and from *captured numerical
behaviour*, never ported line-by-line from the GPL'd reference (notably Mike Brookes's
VOICEBOX and the jointly-copyrighted DYPSA method), so the result is an independent
work rather than a derivative of GPL source. The reference is used only as a
golden-master oracle: MATLAB outputs are captured and the Python is validated
bit-exact / machine-ε against them. Development is human-led and human-reviewed —
every commit is approved individually, authored under the user's own git identity,
with **no `Co-Authored-By: Claude` trailer** (this is project convention, recorded in
CLAUDE.md).

## The working method (this is the important part — keep doing this).

Every step follows the same discipline. Do not skip it to save tokens; it is why the
port has zero silent bugs.

- **Gate before code.** Before writing anything, surface the conventions from the
  MATLAB source — exact formulas, sign conventions, window lengths, index offsets,
  rounding — and stop for review. Structural questions (data-model shape, where a value
  lives, public API) get settled at the gate, not discovered mid-implementation. Gates
  here ran multiple rounds; that's normal and correct.
- **Golden master is the arbiter.** Reference outputs captured from MATLAB; Python
  validated bit-exact / machine-ε against them. Parity is the only pass/fail gate. Tight
  tolerance (rtol ~1e-10..1e-12) regardless of the feature's inherent noise, because
  parity is a deterministic same-input comparison. The one exception seen so far — J2's
  residual join at rtol=1e-9 — is looser only because its ε is accumulated
  BLAS-dependent linear-algebra error, and that reason is documented in-test so nobody
  tightens it into a flaky gate. A loosened tolerance always needs a named, in-test
  reason.
- **Write from the algorithm, not by transliterating.** Reproduce behaviours (numerical
  facts) exactly; do not copy MATLAB code structure line-by-line (that would make it a
  derivative of the GPL source). If the numbers match, the loop structure needn't
  resemble the MATLAB.
- **Synthetic-known-value tests are the second mechanism.** Golden master proves
  "matches the reference." Synthetic tests (constructed input with a hand-computable
  answer) prove "computes what I expect" — they catch cases where the reference itself
  is questionable, and they're the only way to exercise paths no fixture reaches (cold
  degenerate branches). For shared/foundational components they are load-bearing, not
  supplementary. When a test exists to prove an invariant, assert the decomposition, not
  just the final value — a test that checks only the end result can't distinguish
  "computed correctly" from "rescued downstream."
- **Reproduce-and-quarantine reference quirks.** The reference has bugs. Match them
  exactly for parity, but file every one in REFERENCE_NOTES, and — where the correction
  is knowable — quarantine behind a named flag so a later fix is a one-line flip. A
  degenerate path with a defined reference value (even inf/nan from IEEE division) is
  reproduced, not "fixed" with an invented sentinel — inventing a tidier value is a
  silent parity departure.
- **Single-source shared conventions.** When a helper or constant crosses a boundary,
  hoist it to one location. Two copies of a constant is silent-drift — the failure the
  project explicitly guards against. Distinguish coupling (two places that must change
  together — the real hazard) from coincidence (two places that happen to agree with no
  reason to track each other — benign). Never init a to-be-masked array to a value
  that's wrong if the mask misses.
- **Track distinct causes, not distinct symptoms.** When one root cause surfaces in a
  second feature, cross-reference the existing ledger entry — don't open a new one.
- **Commit hygiene.** Split refactors of already-committed code from new code, in
  dependency order, each individually green, so history bisects cleanly. When a refactor
  must be proven behavior-preserving, land the guard test first as a separate commit
  (its pre-refactor baseline), then the refactor — the guard staying green is the proof.
  Never commit without explicit per-commit approval; author under the user's identity
  only, no Claude co-author trailer.

## The reviewer loop.

This work is done with a separate Claude instance acting as thinking-partner and
reviewer (not the implementer). The pattern: the user brings what Claude Code proposes
or reports; the reviewer critiques it, catches what's missed, pushes on structural
decisions, drafts the prompts handed back to Claude Code, and flags the single
load-bearing thing to watch in each round. Several of this project's best outcomes came
from the reviewer catching a decision that would have been expensive to reverse, and
from Claude Code correcting the user's premise. Direct pushback is expected in both
directions. The reviewer's "one thing to watch" per round is a deliberate device — the
single item that fails silently if unattended — and it's worth preserving.

## Where step 6 ended — the orchestration seam as wired

The `GciResult → VoiceFeatures` seam is wired end-to-end and closed:

```
iaif → (yaga → YagaResult.residual, derive_flow) → prepare_cycles
     → four feature groups → apply_cycle_mask → VoiceFeatures
```

Durable properties:
- **One IAIF config site.** The residual is *returned* from `yaga()` as
  `YagaResult.residual` (frozen field, array read-only) — never accepted/injected — so
  the features path reuses that one IAIF run and cannot re-select an `IaifConfig`.
- **One shared per-cycle prep** (`prepare_cycles` → `CyclePrep`): the unshifted `useg`,
  the `uuseg`, the single DC-shifted `useg_shifted` (derived from `useg`), and `O1` are
  computed once. The three segment arrays are deliberately distinct (pa and the spectral
  FFT are shift-invariant, so a merge would still pass the gate — hence the guard
  against collapsing them).
- **O1==0 zeroing** of `{cq, qoq, mfdr, pa, naq}` is a reusable
  `apply_cycle_mask(mask, subset, value)` step: the groups already self-satisfy it
  (leave `0.0` from init, the reference value), and the seam re-covers it redundantly.
  `np.where` selects, never multiplies. `f0`/`framek`/`vuv`/`h1h2`/`hrf` are **not**
  masked.

The four joins, all asserted from the public API:
- **J1** — live `gci` bit-exact vs capture (integer indices); `tests/test_yaga_detector.py`.
- **J2** — live `YagaResult.residual` vs captured `udash`, rtol=1e-9 (the one
  BLAS-dependent, accumulated-linear-algebra join; reason in-test);
  `tests/test_yaga_detector.py`. (J1 and J2 both live here — there is no separate
  end-to-end test file.)
- **J3** — `derive_flow(captured udash) == feat_u`, with independent gain (0.708494
  @16k / 0.709878 @8k) and SciPy arg-order pins; `tests/test_features_flow_derivation.py`.
- **J4** — all ten features composed in one call; the five flow/timing features asserted
  **bitwise** (the refactor guard, which stayed green with its assertion function
  untouched through the shared-prep hoist); `tests/test_features_extract.py`.

## Roadmap position

Steps 1–6 are done (scaffolding; I/O & framing; LPC; IAIF; YAGA GCI/GOI;
voice-feature extraction). **Step 7 (VUV / voicing detection) is next** — one unified,
well-tested approach, and per DESIGN.md it also **closes DYPSA's own bug #5** ("should
have an integrated voiced/voiceless detector"). After it: step 8 (alternative
weighted-LP GIF methods — closed-phase, AME, Gaussian weighting), step 9 (LF-model
fitting, YIN pitch tracking, evaluation/scoring), step 10 (docs, examples, first public
release).

## Step 7's starting constraints — the gate inputs, not scratch

- **C7 is likely a VUV-mask concern.** `dpeak ≤ 0` (a negative-declination *open set*;
  `min(dpeak) = +8.77e-3` on current fixtures, so unexercised) probably belongs to VUV,
  not a flow-group guard: a strictly-positive-residual cycle has no glottal closure and
  is plausibly **unvoiced**. VUV may be where such a cycle gets masked.
- **VUV plugs into the existing `apply_cycle_mask` seam** as a second call — over its
  own subset, with **`nan`** as the value (the uncomputable convention), *not* `0.0`.
  Contrast with the `O1==0` mask, whose value is `0.0` (the reference's degenerate value
  there). No restructuring is needed by design; the seam was built as a general
  `(mask, subset, value)` step precisely so VUV is additive.
- **Two old, never-reconciled implementations.** The prior research code carried two
  voicing implementations that were never reconciled; step 7 is the single unified,
  well-tested replacement (DESIGN.md step 7).
- **Name the two "vuv"s distinctly.** `VoiceFeatures.vuv` today is the *framework
  frame-length flag* (`T ∈ (fs/400, fs/40)`), **not** the step-7 classifier. The
  `src/voicekit/vuv/` module is currently an empty one-line stub. Give the step-7 output
  a distinct name so it can't be conflated with the framework flag.

## Open sub-questions for the step-7 gate (settle at the gate, don't pre-decide)

- **The opening fork — capture-and-match or define-the-target?** Is step 7 a
  *capture-and-match* milestone (the old code has authoritative behaviour to
  golden-master against, so it gates like steps 1–6), or a *define-the-target* milestone
  (the two old implementations disagree, no single authoritative behaviour exists, so
  there is no parity oracle and synthetic-known-value tests become *the* oracle rather
  than the second mechanism)? This decides whether step 7 gates like every prior step or
  differently, so settle it first — everything below depends on the answer.
- Relatedly: if a MATLAB reference for the *unified* VUV does exist, capture-and-match
  applies; if step 7 is a from-scratch unification of the two divergent implementations,
  define-the-target applies and the acceptance criteria must be constructed, not
  captured.
- Does VUV run **per-cycle** (slotting into the existing seam as the second mask) or over
  a **different framing** (windowed/frame-based, not GCI-cycle-aligned)? This decides
  whether it's an `apply_cycle_mask` call at all.

## Ledger pointer

C6 (short-cycle empty DC-shift window), C7 (`dpeak ≤ 0`), the naq `dpeak==0` IEEE-shim
(Reproductions entry), and the F1-misconfiguration lead (the reference detector's fixed 20/4/20 at
8 kHz) all live in `REFERENCE_NOTES.md` — read them there; they are not duplicated here.
The V1–V5 feature-observation ledger and C1–C7 coverage gaps are likewise in
REFERENCE_NOTES.
