# Reference notes: reproduced quirks

This document tracks places where the voicekit-py port deliberately **reproduces**
a specific behaviour of the reference MATLAB implementation (`dypsagoi.m` and the
VOICEBOX functions it calls), including behaviours the reference's own authors
flag as probable bugs.

## Five sections — read this first

Most entries here are **matches to the reference, not divergences from it.** Every
algorithm in this project is validated against captured MATLAB output at
machine-epsilon tolerance ("golden masters"); to pass, the Python must reproduce
what the reference actually computes — quirks included. So a *Reproductions* entry
means *"the port faithfully matches the reference at this point,"* even where that
point diverges from what would be *correct*. Several are annotated as probable bugs
**by the reference's own source comments**, quoted verbatim below. They diverge
from correctness; they do **not** diverge from the reference.

1. **Reproductions** (§ "Reproduced reference quirks"). The port matches the
   reference. Two flavours:
   - *self-flagged reference bugs* — the reference source comments call them
     probable bugs or compatibility hacks; and
   - *deliberate departures from a textbook/library standard* that the reference
     makes and we therefore match (e.g. an alignment convention that differs from
     stock/`PyWavelets` behaviour but is what the reference does).
2. **Divergences** (§ "Divergences from the reference"). Places where the Python
   **deliberately does not** match the MATLAB — a different category entirely.
   **There are none yet.** If one ever appears it gets its own entry there with a
   dated rationale and the accuracy result that justified it.
3. **Coverage gaps** (§ "Coverage gaps — reproduced-but-unexercised paths"). Code
   paths implemented from the source and believed correct, but which **no captured
   fixture exercises** — so the golden master is *silent* on them. Neither
   reproductions (the port isn't matching a known-odd reference behaviour) nor
   divergences (the port doesn't differ): places where "bit-exact on all three
   fixtures" genuinely does not cover the path.
4. **Fixture limitations** (§ "Fixture limitations — captures that don't reproduce
   end-to-end"). The *inverse* of a coverage gap: a fixture whose captured output the
   **correct** code cannot reproduce end-to-end, because the capture itself rests on a
   synthetic substitution. The code isn't wrong and the path isn't unexercised — the
   fixture's end-to-end anchor is simply not a faithful capture of the live pipeline.
5. **Feature observations** (§ "Feature observations — a developing reference"). Like
   the reproduced-quirk entries, but for the voice-feature reference
   (`extractVoiceFeatures.m`), which is at an earlier developmental stage and likely
   carries small unironed issues (time-shifts, normalizations). These are **matched
   faithfully** like everything else; the entries record the doubt as an overview to
   revisit when the reference stabilizes. Unlike entries 1–5 they generally **do not**
   specify a correction — the point is to catalogue oddities, not fix them — except
   where a fix happens to be knowable (a plain variable swap).

A future reader must not misread a "quirk reproduced" entry as "the port differs
here." It does not: it matches. And must not read "passes every unit test" as
"fully exercised" — see the coverage-gaps section for where it isn't.

**Convention:** the inline code comment at each reproduction site should point
back to this file (e.g. `# see REFERENCE_NOTES.md: waveform window +1`) rather
than re-explaining the quirk, so the rationale lives in one place.

**Status field** lets an entry later flip from *reproduced* to *corrected*: once
corpus-accuracy numbers (APLAWD / OpenGlot) exist, a correction candidate may be
changed to deliberately diverge from the reference — at which point its status
becomes `corrected — diverges from ref as of <date>, because <accuracy result>`
and the entry moves to the Divergences section.

---

## Reproduced reference quirks

### 1. Waveform-similarity window: asymmetric `+1` upper endpoint

- **Where:** DP waveform-similarity cost kernel (`voicekit.yaga` sub-piece 1);
  reference `dypsagoi.m`, `wavix` definition.
- **What the reference does:** the cross-correlation window is
  `wavix = -floor(nxc/2) : floor(nxc/2)+1` — asymmetric, one extra sample on the
  right (e.g. `-80..81`, 162 samples, at 16 kHz).
- **Reference self-comment (verbatim):**
  ```
  % rather complicated window specification is for compatibility with DYPSA 2
  % === +1 below is for compatibility - probably a bug
  wavix=(-floor(nxc/2):floor(nxc/2)+1)';                 % indexes for segments [nx2,1]
  ```
- **Port:** reproduces the asymmetric window exactly (required for `mycost[:,0]`
  parity).
- **Status:** reproduced (validation-phase correction candidate).

### 2. Waveform-similarity `(nx2-1)/(nx2-2)` bias factor

- **Where:** DP waveform-similarity cost kernel (`voicekit.yaga` sub-piece 1);
  reference `dypsagoi.m`, `q_cas` computation.
- **What the reference does:** the normalized cross-correlation is scaled by
  `-0.5*(nx2-1)/(nx2-2)`; the `(nx2-1)/(nx2-2)` factor exists only to match a bug
  in a superseded helper (`swsc`). The reference's own revision history lists
  removing it as a planned change.
- **Reference self-comment (verbatim):**
  ```
  % === the factor (nx2-1)/(nx2-2) is to compensate for a bug in swsc()
  ```
  and, in the file's revision-history header:
  ```
  %        10. Incorporate -0.5 factor into dy_wxcorr and abolish erroneous (nx2-1)/(nx2-2) factor
  ```
- **Port:** reproduces the factor exactly (required for `mycost[:,0]` parity).
- **Validation-phase note:** this factor has a documented removal-and-return
  history — the revision-history line above shows a prior revision *removed* it
  ("abolish erroneous …"), yet it is live again at the `q_cas` line. So a
  previous revision actually ran without it: the correction experiment (rerun
  against APLAWD with the factor removed) is already half-designed by the
  source's own history, making this the correction candidate with the clearest
  prior art.
- **Status:** reproduced (validation-phase correction candidate).

### 3. Penultimate-candidate traceback force

- **Where:** DP traceback (`voicekit.yaga` sub-piece 3); reference `dypsagoi.m`,
  start of the traceback.
- **What the reference does:** instead of tracing back from the best
  end-of-spurt node (`f_fb(Ncand+1)`), it forces acceptance of the penultimate
  candidate and picks the best of it. This is one source of the odd first/last
  GCI intervals seen in every fixture.
- **Reference self-comment (verbatim):**
  ```
  % === for compatibility with dypsa2, we force the penultimate candidate to be accepted
  % === should be: i=f_fb(Ncand+1) but instead we pick the best of the penultimate candidate
  ```
- **Port:** reproduces the forced penultimate-candidate traceback (required for
  `gci_dp` parity).
- **Validation-phase note:** the reference does not merely flag this — it states
  the corrected form: the traceback should start from `i = f_fb(Ncand+1)` (the
  best end-of-spurt node) rather than the forced penultimate candidate. This is
  the best-documented of the five (flagged, explained, *and* the fix given), so
  the validation-phase worklist already has the concrete change and it is the
  low-effort correction when the time comes.
- **Location confirmed (step 0′ internal capture):** the quirk lives entirely in
  the **traceback**, not the forward pass. Both the quirk and the corrected
  (`f_fb(Ncand+1)`) start nodes walk back through the *same* captured forward-pass
  tables (`dp_fc`/`dp_ff`/`dp_fpq`/`dp_ffb`), which are computed identically
  regardless of the traceback's start-node choice. So the forward-pass arbiter is
  quirk-free, and sub-piece 2's recursion test cannot be contaminated by this
  quirk; it is purely a sub-piece-3 (traceback) concern.
- **Exercised on `vowel_glide_16k`:** reconstructing the traceback both ways from
  the captured tables, the corrected `f_fb` start yields 62 GCIs versus the
  quirk's 63. The extra GCI is **spurious** — the corrected path is exactly the
  quirk path with its first GCI removed, so the forced-penultimate start prepends
  one false glottal closure that the corrected form does not. On
  `vowel_f0100_16k` and `vowel_f0120_8k` the two agree (penultimate == best-end
  there), so the effect is real but fixture-dependent. The correction is therefore
  now **both source-specified** (the reference states `i = f_fb(Ncand+1)`) **and
  fixture-demonstrated** (glide shows the quirk emitting a spurious GCI the fix
  removes) — no longer a comment-only candidate but one with a reproduced,
  measurable symptom.
- **Status:** reproduced (validation-phase correction candidate).

### 4. SWT one-sample alignment offset (`swtalign`)

- **Where:** stationary wavelet transform (`voicekit.yaga.swt`); reference
  `dypsagoi.m`, `swtalign` subfunction.
- **Category:** *deliberate departure from a textbook/library standard*, not a
  self-flagged bug. Stock MATLAB `swt` (and `PyWavelets`' SWT) keep the
  coefficients with a `lf+1` alignment; `swtalign` uses `lf`, shifting the
  multiscale coefficients by one sample. The downstream group-delay and DP
  stages are tuned to this alignment, so it is the intended behaviour, not an
  error — and it is why our SWT does not match `PyWavelets` at the boundary
  (`PyWavelets` is used in tests only to check the filter *taps*, never the
  transform).
- **Reference self-comment (verbatim):**
  ```
  %SWT Discrete stationary wavelet transform 1-D. Differs from swt(...) in
  %alignment of multiscale coefficients
  ```
  and, at the coefficient-keep line:
  ```
      swd(k,:) = wkeep1(wconv1(x,hi),s,lf);   % Default last arg was lf+1.
  ```
- **Port:** reproduces the `lf` (one-sample-earlier) alignment exactly.
- **Status:** reproduced (deliberate departure from textbook; intended behaviour,
  **not** a correction candidate).

### 5. GOI post-processing pairing (`postGOI`)

- **Where:** GOI post-processing in `voicekit.yaga.detector` (`_goi_postprocess`);
  reference `dypsagoi.m`, the `postGOI` block. The unresolved bug already
  acknowledged in [DESIGN.md](DESIGN.md) §1.
- **What the reference does:** after the GOI dynamic program produces opening
  candidates, `postGOI` tries to enforce strict `GCI-GOI-GCI-GOI` alternation. It
  interleaves GCIs (label +1) and GOIs (−1) sorted by position and uses
  `fftfilt([1 1], k)` as a 2-tap adjacency detector: where two GCIs are adjacent
  (sum +2, a closure with no opening after it) it **adds** an opening at
  `gci_position + previous-opening-period`; where two GOIs are adjacent (sum −2)
  it **removes** the stray one.
- **Reference self-comment (verbatim):**
  ```
  % NEEDS FIXING - DOESN'T ALWAYS GIVE EQUAL GCIS AS GOIS
  ```
- **Two distinct symptoms, and their coverage:**
  - *`-1` sentinels* — when a GCI needs an opening added but there is **no previous
    opening** (signal start), the "closest previous GOI" lookup returns empty and
    the MATLAB insertion `[[] ; -1]` collapses to a scalar `-1`, which is broadcast
    to both the position and label rows — so an opening at position `-1` is emitted.
    Fires on **all three** fixtures (2, 2, 1 sentinels).
  - *count mismatch* — the add/remove operations do not balance, so
    `len(goi) != len(gci)`. Fires on **glide only** among these three (64 vs 63).
- **Port:** reproduces the pairing exactly — the raw `goi` matches the capture
  including the sentinels and the mismatch. Quarantined behind
  `YagaConfig.goi_postprocess` (default `True`). **`True` reproduces this bug for
  golden parity; `False` skips the pairing step entirely (raw sorted GOI-DP
  output) — which is *not* the fix: it drops the alternation-enforcement feature
  along with the bug. The correct behaviour (boundary-aware pairing) is in neither
  branch** and is validation-phase work. The public `GciResult.goi` never carries
  the `-1` sentinels: they are dropped when the raw sequence is aligned to a
  per-cycle representation (`NaN` for an unpaired cycle); only the raw parity path
  reproduces them.
- **Fix spec (the mechanism is the spec, as with entry 3):** handle the
  no-previous-opening boundary so no invalid position is emitted; acceptance = no
  `-1` sentinels and `len(gci) == len(goi)`.
- **Status:** reproduced (validation-phase correction candidate). Symptoms are
  exercised (not a coverage gap): sentinels on all three fixtures, count mismatch
  on glide.

---

## Divergences from the reference

Places where the Python port **deliberately** does not match the reference, with a
dated rationale and the accuracy result that justified the change.

**None yet.** The port matches the reference everywhere; correction candidates
above are revisited once corpus-accuracy numbers exist.

---

## Coverage gaps — reproduced-but-unexercised paths

Code paths implemented from the reference source and believed correct, but which
**no committed fixture traverses**. The unit-test suite validates every algorithm
against captured MATLAB output at machine-epsilon tolerance — but the fixtures are
small, clean, continuous synthetic vowels, and they structurally do not reach these
branches. So for the paths below, *"bit-exact on all three fixtures" does not cover
them*: the golden master is silent, and the code is trusted on a source reading
alone.

This section doubles as a **validation-phase worklist**: these are the paths that
pass every unit test but that real speech will first stress. Corpus validation
(OpenGlot / APLAWD) is the likely first real exerciser — multi-spurt utterances,
varied glottal-cycle spacing, and quantization artifacts almost certainly appear
there — so each entry records the concrete input characteristic that would drive the
path, to make going and finding it deliberate rather than incidental.

### C1. Phase-slope projection: flat (`sign(gdotdot)==0`) turning point

- **Where:** `voicekit.yaga.phase_slope`, turning-point min/max classification.
- **Why the fixtures miss it:** classification reads `sign(gdotdot)` at the
  extremum; on the smooth synthetic group-delay function an extremum is never
  exactly flat, so `gdotdot` is always strictly non-zero there and every turning
  point classifies as a clean min or max. The `sign(gdotdot)==0` branch (a turning
  point that is neither) is never taken.
- **What would exercise it:** a group-delay function with an exactly flat spot at an
  extremum — e.g. from a clipped or coarsely quantized residual producing a plateau
  in `gdwav` at a local extremum.

### C2. Closed-phase cost: adjacent / degenerate-interval candidates

- **Where:** `voicekit.yaga.dp_costs.closed_phase_cost`, the inclusive
  inter-candidate range mean.
- **Why the fixtures miss it:** the mean is taken over `u[pos_i : pos_{i+1}+1]`; the
  clean vowels space candidates a full glottal cycle apart, so every interval is
  long and the adjacent case (two candidates at the same or neighbouring samples,
  giving a one-sample — or would-be empty — interval) never occurs. The orthogonal
  unit test constructs it, but no fixture does.
- **Not gated by the DP (negative finding, sub-piece 2):** the DP's `qmin`/`qrmin`
  minimum-period constraint might look like it prevents this, but it does **not**.
  `qmin` gates *path linkage* — which previous GCI may precede a candidate — not the
  *spacing of the assembled candidate list*, which is what the closed-phase mean
  iterates over. Assembly never enforces a minimum separation, so a reader must not
  assume the DP's minimum period protects the closed-phase path: it is purely an
  assembly-level reachability question (can assembly emit adjacent candidates?).
- **What would exercise it:** a signal with very short inter-candidate spacing — two
  glottal-closure candidates one or zero samples apart (e.g. a doubled/creaky pulse
  or a projected candidate landing on a zero-crossing one).

### C3. Pitch-deviation kernel: mid-signal talkspurt-start row (`k >= 2`)

- **Where:** `voicekit.yaga.dp_kernels.pitch_deviation` and its spurt-separation
  test.
- **Why the fixtures miss it:** a talkspurt start carries `dy_cspurt` instead of the
  pitch kernel's value, identified by previous period 0. On the continuously voiced
  vowels the only spurt start on the *selected path* is at the utterance beginning
  (`k = 0, 1`), which is outside the pitch kernel's `k >= 2` domain. So the
  sub-piece-1 spurt-separation set-equality test only ever runs in its **empty-set**
  form — it confirms the kernel matches every in-domain row, but never a case where
  an in-domain *selected-path* row is a spurt start.
- **Partially closed at the recursion level (sub-piece 2):** the DP forward pass
  marks a spurt start with `f_pq == 0`, and the captured `dp_fpq` shows these on
  **interior candidates**, not only path edges (7 interior spurt-start nodes on
  `vowel_f0100_16k`). Sub-piece 2 asserts the recursion's `f_pq == 0` node set
  equals the capture exactly, so the spurt-*marking* rule **is** validated in-domain
  at the trellis level. What remains open is a spurt start on the **selected path**
  mid-signal — the pitch-row / traceback case above.
- **What would exercise the remaining gap:** a multi-spurt utterance — silence or
  unvoiced material mid-signal, then voicing resumes — which puts a talkspurt-start
  row on the chosen path at `k >= 2`, giving the selected-path set-equality a
  non-empty spurt set to separate.

---

## Fixture limitations — captures that don't reproduce end-to-end

A fixture whose captured output the **correct** code cannot reproduce when the full
pipeline is run live, because the capture was produced with a synthetic substitution
rather than the real upstream stage. This is not a code bug (the code is right) and
not a coverage gap (the path *is* exercised) — it is a property of the *fixture*: its
end-to-end anchor is not a faithful capture of the live pipeline, so it validates
stage-isolated parity and composition *sanity*, but not composition *exactness*.

### F1. `vowel_f0120_8k` — end-to-end capture rests on a clean-residual injection

- **Where:** the 8 kHz fixture's end-to-end `gci` capture; `voicekit.yaga.yaga` on
  8 kHz input.
- **What happened:** the reference MATLAB IAIF returns a NaN residual tail at 8 kHz
  (an intrinsic reference failure — see `tests/golden/README.md`, "The 8 kHz fixture
  bypasses IAIF"), so the capture substitutes a clean synthetic ground-truth residual
  for the IAIF estimate. Every stage *downstream of IAIF* was then captured on that
  clean residual and is valid for stage-isolated parity. But `yaga()` run live uses
  the real (from-scratch, NaN-free) IAIF, whose 8 kHz residual differs from the
  injected one (correlation ~0.83), so the live end-to-end `gci` does **not** match
  the captured `gci`.
- **Consequence:** `vowel_f0120_8k` is used for **stage-isolated** parity (SWT, group
  delay, psp, costs, forward pass, traceback, refine — all bit-exact on captured
  inputs) and for end-to-end **runs-and-sane** (the pipeline completes and yields
  plausible voiced GCIs: F0 ≈ 120 Hz, uniform periods), but **not** for end-to-end
  bit-exactness. The two 16 kHz fixtures carry the end-to-end exactness proof (their
  captured residual is real IAIF output, which the live IAIF reproduces bit-exact).
- **Origin:** this is exactly the consequence flagged when the 8 kHz fixture was
  regenerated as a *per-stage-parity* fixture rather than an *end-to-end anchor* (its
  `udash` is the ground-truth residual, not an IAIF output; see
  `tests/golden/README.md`). It is recorded here, not papered over.
- **Not fixed by API:** `yaga()` deliberately has **no** residual-injection parameter
  to force 8 kHz to match — that would be shaping production code to a fixture's
  workaround. The limitation stands as documented instead.

---

## Feature observations — a developing reference

The voice-feature reference (`vsaTools/extractVoiceFeatures.m`) replicates several
papers (Patel 2011, Laukkanen 1996, Alku for NAQ) and is at an earlier
developmental stage than `dypsagoi.m` — it likely carries small unironed issues.
The port **matches it exactly** (golden-master parity is the only gate); these
entries catalogue where the reference diverges from a published definition, sorted
by whether the divergence is an *explained convention* or looks like an *unironed
issue*. They are an overview to read when the reference stabilizes, and generally
do **not** specify a correction — the reference is still developing, so the correct
behaviour is not yet settled. A synthetic known-value check (not a gate) is what
surfaces each one.

### V1. F0 uses `fs/(period-1)`, not `fs/period`

- **Where:** `voicekit.features.framework` (`cycle_framework`); reference
  `extractVoiceFeatures.m`, the per-cycle loop.
- **What the reference does:** the period is `T = len(nn) - 2` where `nn` is the
  inclusive sample range of a cycle, and `f0 = fs/T`. For an interior cycle spanning
  `period` samples between consecutive GCIs, `len(nn) = period + 1`, so `T = period - 1`
  and `f0 = fs/(period-1)` — not `fs/period`.
- **Surfaced by:** the synthetic constant-pitch check — closures every 160 samples at
  16 kHz (true pitch 100 Hz) yield `f0 = fs/159 = 100.63 Hz`, a ~0.63 % overestimate.
  Parity against the reference reproduces this faithfully; the synthetic check is what
  shows it departs from `fs/period`.
- **Definition sort:** unexplained — reads like an off-by-one in the period count
  (`len(nn)-2`), but a defensible intent (excluding the two boundary GCI samples) can't
  be ruled out. Reproduced faithfully; correction uncertain pending upstream.
- **Status:** reproduced (feature observation, no correction specified).
