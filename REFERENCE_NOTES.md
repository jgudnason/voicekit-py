# Reference notes: reproduced quirks

This document tracks places where the voicekit-py port deliberately **reproduces**
a specific behaviour of the reference MATLAB implementation (the reference GCI/GOI
detector and the VOICEBOX functions it calls), including behaviours the reference's own authors
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
   (the reference feature-extraction pipeline), which is at an earlier developmental stage and likely
   carries small unironed issues (time-shifts, normalizations). These are **matched
   faithfully** like everything else; the entries record the doubt as an overview to
   revisit when the reference stabilizes. Unlike entries 1–5 they generally **do not**
   specify a correction — the point is to catalogue oddities, not fix them — except
   where a fix happens to be knowable (a plain variable swap).

A future reader must not misread a "quirk reproduced" entry as "the port differs
here." It does not: it matches. And must not read "passes every unit test" as
"fully exercised" — see the coverage-gaps section for where it isn't.

Beyond these five (which are all port-vs-reference), a trailing **Step 7 (VUV) —
forward findings** section records watch-items surfaced while designing the
in-progress voicing milestone. Those are design findings for an as-yet-unbuilt
component, not reproduction facts.

**Convention:** the inline code comment at each reproduction site should point
back to this file (e.g. `# see REFERENCE_NOTES.md: waveform window +1`) rather
than re-explaining the quirk, so the rationale lives in one place.

**Naming & provenance convention** (authority: CLAUDE.md "Provenance", which
scopes the rule to the private trees by name): the prior MATLAB research code —
a private working tree of prior research code — is private and
unpublished, so this file refers to its files generically ("the reference
weighted-GIF driver", "the reference GOI-selection step"), never by filename. It
is the private *filename* that is withheld, not the *method*: published
algorithms, and methods being published as part of voicekit, are described freely
and in full mechanism. Published prior work stays named (VOICEBOX and its
`v_`-functions, the DYPSA method, papers), and voicekit's own API names may echo
the MATLAB names. Entries written before 2026-07-19 may still carry private
filenames; a genericization sweep (filenames only, method content untouched) is
a ledgered follow-up.

**Status field** lets an entry later flip from *reproduced* to *corrected*: once
corpus-accuracy numbers (APLAWD / OpenGlot) exist, a correction candidate may be
changed to deliberately diverge from the reference — at which point its status
becomes `corrected — diverges from ref as of <date>, because <accuracy result>`
and the entry moves to the Divergences section.

---

## Reproduced reference quirks

### 1. Waveform-similarity window: asymmetric `+1` upper endpoint

- **Where:** DP waveform-similarity cost kernel (`voicekit.yaga` sub-piece 1);
  the reference detector, `wavix` definition.
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
  the reference detector, `q_cas` computation.
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

- **Where:** DP traceback (`voicekit.yaga` sub-piece 3); the reference detector,
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

- **Where:** stationary wavelet transform (`voicekit.yaga.swt`); the reference
  detector, `swtalign` subfunction.
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
  the reference detector, the `postGOI` block. The unresolved bug already
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

### 6. NAQ silent IEEE division when `dpeak == 0`

- **Where:** `voicekit.features.flow` (`flow_statistics`), the `naq` division
  `fac / (dpeak * t_time)`; the reference feature-extraction pipeline, the per-cycle `else`
  branch.
- **What the reference does:** when a cycle *has* an open phase (`O1 != 0`) but its
  flow derivative grazes zero at the minimum (`dpeak = -min(uuseg) == 0`), MATLAB
  evaluates `fac/(dpeak*Ttime)` and returns `Inf` (for `fac > 0`) or `NaN` (for
  `fac == 0`) — **silently**, MATLAB's `x/0` raising no warning. The reference has a
  *defined* value on this path, so this is parity, not a degeneracy to invent a
  sentinel for.
- **Port:** reproduces the value exactly (numpy's IEEE division gives the same
  `Inf`/`NaN`). The only divergence is diagnostic — numpy *warns* where MATLAB is
  silent — so the division is wrapped in `np.errstate(divide="ignore",
  invalid="ignore")`: a scoped MATLAB-compat shim over the one line whose only
  operands are `fac`/`dpeak`/`t_time`, suppressing nothing but this enumerated case.
  A `nan` sentinel was **rejected**: the reference's value is `Inf`/`NaN` by IEEE, and
  `nan` would also collide with the codebase's NaN-for-absent convention
  (`GciResult.goi`), conflating "no such event" with "unbounded ratio."
- **Reachability:** `dpeak == 0` exactly is **measure-zero on real data** (it needs a
  bit-exact-zero `uuseg` minimum) and is reachable only by construction; on the
  fixtures every cycle has `dpeak > 0` (min +8.77e-3 — see C7 for the neighbouring
  `dpeak < 0` open set). Exercised by an orthogonal unit test
  (`test_features_flow.py`), not a fixture.
- **Status:** reproduced (matches MATLAB IEEE division; not a correction candidate —
  the reference's behaviour here is defined, not buggy).

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

### C4. Feature timing: the `O1==0` no-open-phase zeroing

- **Where:** `voicekit.features.timing` (`timing_statistics`, the `O1==0` branch);
  the reference feature-extraction pipeline, the per-cycle loop. Subsumes the flow group's
  deferred note: this one branch governs **five** features at once.
- **What the reference does:** when `openclosetimings` finds no open phase
  (`openPeriods` returns no rising edge, so `O1==0`), the reference zeroes the cycle's
  `cq`, `qoq`, `mfdr`, `pa`, `naq` — but **not** `f0` (it still sets `f0 = 1/Ttime`),
  nor `vuv`/`framek`/`h1h2`/`hrf`. So the degenerate branch masks the five
  timing/flow features and leaves the framework and spectral ones untouched.
- **Why the fixtures miss it:** every cycle on all three fixtures has a clear open
  phase — the 5%-of-peak threshold crossing survives the median filter on all of
  them (0 cycles with `cq==0`, the `O1==0` signature). The clean synthetic vowels
  simply never produce a fully-closed / degenerate cycle, so the zeroing is
  reproduced from the source but never taken on captured data. (`timing_statistics`
  currently owns the branch; the flow group's identical zeroing is applied at
  orchestration once `O1` is shared — the same untraversed path either way.)
- **Exercised by an orthogonal unit test, not a fixture:** `test_features_timing.py`
  constructs a flat cycle (no threshold crossing) and asserts `open_close_timings`
  returns `O1==0` and `timing_statistics` zeroes `cq`/`qoq`. So the branch is not
  untested — but "bit-exact on all three fixtures" does not cover it.
- **What would exercise it on real data:** a cycle with no detectable open phase — a
  fully-closed or near-silent glottal cycle, or one whose flow pulse is so small or
  noisy that no sample clears 5% of the (shifted) peak after median filtering. Creaky
  or breathy phonation and inter-word closures in corpus speech are the likely first
  exercisers.

### C5. Spectral features: the `number_partials <= 1` degenerate guard

- **Where:** `voicekit.features.spectral` (`spectral_params`, the guard); the reference
  feature-extraction pipeline, `specParam`.
- **What the reference does:** `number_partials = floor(harmonic_limit/f0)` counts
  the harmonics below 3000 Hz. When `number_partials <= 1` (at most H1 below the
  limit) both features return a **literal `0`** — not NaN. This guards the
  `partial_amplitudes(2)` / dB-sum access against there being no second harmonic.
- **The `0` does not map to the `VoiceFeatures` NaN convention.** Elsewhere an
  uncomputable cycle is `NaN`; here the reference deliberately writes `0`, so the
  port writes `0` too (parity), and a consumer sees a real zero in `h1h2`/`hrf` (i.e.
  the crossed HRF/H1-H2) for such a cycle, not `NaN`.
- **Why the fixtures miss it:** the guard trips only for `f0 > 1500 Hz` (so that
  `floor(3000/f0) <= 1`). Every fixture cycle has `number_partials >= 6` (f0 well
  under 300 Hz), so the branch is reproduced from the source but never taken on
  captured data.
- **Exercised by an orthogonal unit test, not a fixture:** `test_features_spectral.py`
  calls `spectral_params` with `period=8` at 16 kHz (f0 = 2000 Hz → one partial) and
  asserts the `(0.0, 0.0)` return.
- **What would exercise it on real data:** a cycle with f0 above ~1.5 kHz — a
  soprano's top register, a child's cry, or a creaky/octave-jump cycle whose measured
  period is very short.
- **Orthogonal to C4 (`O1==0`), by mechanism not coincidence:** C5 trips on the partial
  *count* (`f0 > 1500 Hz`), C4 on the *open-phase* detection — independent conditions.
  The C4 seam test (`tests/test_features_extract.py`,
  `test_c4_o1_zero_cycle_decomposition`) constructs a **long-period** no-open-phase
  cycle (`number_partials = 37`) so it takes C4 without tripping C5; C5's own test takes
  a short period. The two degenerate returns (C4 zeros the five timing/flow features;
  C5 returns literal `0` for the two spectral features) never conflate.

### C6. Short cycle: empty DC-shift window (`mean of empty slice` / `medfilt` warning)

- **Where:** `voicekit.features.prep` (`prepare_cycles`), the DC-shift
  `useg[lo-1:hi].mean()` with `lo = round(0.1*T)`, `hi = round(0.3*T)`; and the
  downstream `medfilt` inside `open_close_timings`.
- **What happens:** for a **very short** cycle (`T` a handful of samples), the
  `[10%, 30%]` window `useg[lo-1:hi]` is empty, so `.mean()` emits
  `RuntimeWarning: Mean of empty slice` and returns `nan` (poisoning `useg_shifted`),
  and `medfilt(mask, 7)` on a sub-7-sample segment emits
  `UserWarning: kernel_size exceeds volume extent`. **Distinct from C4:** this is a
  degenerate *period*, not a degenerate *open phase*. Currently **unguarded**.
- **Why the fixtures miss it:** the clean vowels space GCIs a full glottal cycle apart,
  so every cycle (including the two boundary partials) is comfortably long. Kin to the
  C2 adjacent-candidate gap — the two would be driven by the same input (GCIs a few
  samples apart: creak, an octave error, or a projected candidate landing next to a
  real one).
- **Status:** filed, not fixed — a guard (skip or sentinel the sub-window cycle) is
  validation-phase work once corpus data first produces a near-degenerate period.

### C7. Flow declination sign: `dpeak <= 0` (non-negative residual over a cycle)

- **Where:** `voicekit.features.flow` (`flow_statistics`), `dpeak = -min(uuseg)`.
- **What happens:** if the flow derivative never goes negative across a cycle
  (`min(uuseg) > 0`), then `dpeak < 0`, so `mfdr = dpeak/1000` is **negative**
  (physically meaningless) and `naq = fac/(dpeak*T)` is negative — with no zero-divide,
  no warning, and no guard. This is an **open set**, not measure-zero (C7 differs from
  the `dpeak == 0` shim below): it needs only "no sample below zero" across the cycle.
- **Why the fixtures miss it:** every cycle of all three fixtures has a clear negative
  flow-derivative excursion (the glottal closure). Measured `min(dpeak)` across all
  cycles of all three fixtures is **+8.77e-3** — strictly positive, so no cycle
  approaches the sign flip.
- **Likely a VUV concern, not a flow-group guard:** a strictly-non-negative-derivative
  cycle has no closure — plausibly **unvoiced**. So the correct masking layer for it is
  probably the step-7 voiced/unvoiced mask (which the seam's `apply_cycle_mask` already
  accommodates as a second `(mask, subset, value)` call), not a sign clamp inside
  `flow_statistics`. Filed for when VUV lands.

### C8. Covariance LPC: short-frame order reduction (`pp = min(p, nc-d0)`)

- **Where:** `voicekit.lpc.lpc_covar` vs VOICEBOX `v_lpccovar` (line 109,
  `pp=min(p,nc-d0)`), reached via the VUV features' covariance-LPC call.
- **The divergence:** for a frame shorter than the analysis order (`nc <= p`, or
  `nc <= p+1` with `dc_offset`), `v_lpccovar` **silently reduces the order** to fit
  what the frame supports; `lpc_covar` instead **raises** (`too short for order`).
  We keep the raise — a silent order reduction is a worse failure mode than an
  explicit error for a library primitive.
- **Why the fixtures miss it:** every VUV frame is 512 samples (32 ms at 16 kHz)
  against order 16, so `nc >> p` always and the reduction never triggers. No
  fixture exercises a frame short enough to reach it.
- **Status:** unexercised divergence, filed. A step-8 weighted-LP GIF method that
  frames shorter (e.g. a narrow closed phase) could hit `nc <= p` and would need
  this reconciled — reduce order to match the reference, or raise deliberately
  with a documented divergence. Find this entry before framing short.

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
  parity. The two 16 kHz fixtures carry the end-to-end proof — with a precision
  distinction that must not be overstated: the **GCIs and GOIs are bit-exact** (integer
  sample indices), but the live IAIF `residual` matches the captured `udash` only to
  **floating-point ε** (rel ~1e-12), and every float feature derived from it likewise.
  "Bit-exact" at 16 kHz means the *integer* GCI/GOI indices; `udash` and the features
  are ε, not bitwise. (The residual ε is the one join whose error is accumulated,
  BLAS-dependent linear algebra — see the J2 note in `tests/test_yaga_detector.py`.)
- **Origin:** this is exactly the consequence flagged when the 8 kHz fixture was
  regenerated as a *per-stage-parity* fixture rather than an *end-to-end anchor* (its
  `udash` is the ground-truth residual, not an IAIF output; see
  `tests/golden/README.md`). It is recorded here, not papered over.
- **Not fixed by API:** `yaga()` deliberately has **no** residual-injection parameter
  to force 8 kHz to match — that would be shaping production code to a fixture's
  workaround. The residual is *returned* from `yaga()` (as `YagaResult.residual`,
  read-only), never accepted, so no injection seam exists. The limitation stands as
  documented instead.
- **Possible root cause — reference misconfiguration, not an intrinsic 8 kHz limit
  (validation-phase, filed not chased):** the IAIF reference (note 6) recommends `p=8; g=2; r=8`
  at 8 kHz, but the reference detector calls IAIF as `iaif(s, fs, 20, 4, 20, 1)` at **every** rate — a
  20th-order vocal-tract LPC over a 4 kHz band at 8 kHz. That over-ordering is a
  plausible ill-conditioning route to the NaN residual tail this fixture works around,
  which would make F1 a *reference-configuration* artifact rather than a fundamental
  8 kHz failure. The port faithfully mirrors the reference detector's 20/4/20 at all rates
  (`YagaConfig._default_iaif_config`); revisiting the 8 kHz order is validation-phase
  work, not this milestone's.

---

## Feature observations — a developing reference

The voice-feature reference pipeline replicates several
papers (Patel 2011, Laukkanen 1996, Alku for NAQ) and is at an earlier
developmental stage than the reference detector — it likely carries small unironed issues.
The port **matches it exactly** (golden-master parity is the only gate); these
entries catalogue where the reference diverges from a published definition, sorted
by whether the divergence is an *explained convention* or looks like an *unironed
issue*. They are an overview to read when the reference stabilizes, and generally
do **not** specify a correction — the reference is still developing, so the correct
behaviour is not yet settled. A synthetic known-value check (not a gate) is what
surfaces each one.

### V1. F0 uses `fs/(period-1)`, not `fs/period`

- **Where:** `voicekit.features.framework` (`cycle_framework`); the reference
  feature-extraction pipeline, the per-cycle loop.
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

### V2. QOQ divides a duration by an index: `qoq = (C2-O2)/O2`

- **Where:** `voicekit.features.timing` (`timing_statistics`); the reference
  feature-extraction pipeline, the per-cycle loop.
- **What the reference does:** the quasi-open quotient is
  `qoq = (C2-O2)/O2`, where `O2`/`C2` are the start/end **sample indices** of the
  quasi-open phase within the cycle. The numerator `C2-O2` is the quasi-open
  *duration* (samples); the denominator `O2` is an absolute *index* (the quasi-open
  onset, `O2_sub + O1`), **not a duration**. Per Laukkanen (1996) the QOQ is the
  quasi-open duration normalized by a duration — the period `T` (or the cycle
  length) — so the denominator is dimensionally wrong: a duration over an index.
- **Reference self-comment (verbatim):** the reference's own author noticed the
  symptom and left a runtime warning rather than fixing the denominator —
  ```
  if any(qoq>1)
      disp(['Warning: Cycle ' num2str(find(qoq>1)) ' has QOQ>1'])
  end;
  ```
  This is what makes V2 *author-known-but-unironed* rather than merely suspected.
- **V2 is the mechanism behind the scattered QOQ>1 values.** A genuine quotient of
  durations is bounded in `(0, 1)`; here `qoq > 1 ⟺ C2 > 2·O2` (the quasi-open phase
  starts early enough — small onset index `O2` — that its duration exceeds it). The
  fixtures show these directly: 3 cycles on `vowel_f0100_16k` (up to **1.958**), 1 on
  `vowel_glide_16k`, 2 on `vowel_f0120_8k`. **These are not an edge artifact** — they
  are V2 doing exactly what its denominator forces, so a future reader must not
  re-investigate the `QOQ>1` cycles as a boundary bug; they trace entirely to the
  index denominator.
- **Definition sort:** unexplained — an index in a denominator where a duration
  belongs reads like an unironed issue, corroborated by the author's own warning.
  Reproduced faithfully (golden parity is the only gate). The Laukkanen-correct
  denominator (a duration, e.g. `T`) is *knowable* but the reference is still
  developing, so no correction is specified.
- **Status:** reproduced (feature observation, no correction specified).

### V3. H1-H2 and HRF are stored crossed (the wrong feature under each name)

- **Where:** `voicekit.features.spectral` (`spectral_statistics`); the reference
  feature-extraction pipeline, the `specParam` call site.
- **What the reference does:** `specParam` returns `[hrf, h1h2]` (in that order),
  correctly computed. The caller assigns them under **swapped names**:
  ```
  [hrfx, h1h2x] = specParam(useg,T,fs);
  h1h2(ig)=hrfx;     % the array named h1h2 receives HRF
  hrf(ig)=h1h2x;     % the array named hrf receives H1-H2
  ```
  So the stored `h1h2` array holds the **harmonic richness factor** and the stored
  `hrf` array holds the **H1-H2 level difference** — each feature is saved under the
  other's name. This is not a shifted or mis-scaled value: it is *the wrong feature
  entirely* under each label.
- **The capture is crossed, so parity requires the swap.** The golden `.npz` saved
  the reference's stored arrays, i.e. already swapped (verified: the port's HRF
  output matches captured `feat_h1h2`, and does **not** match captured `feat_hrf`).
  The port therefore reproduces the crossing to pass parity; **the uncrossing is not
  applied** (it would break the golden gate), only documented. The swap is performed
  once, visibly, at the assignment in `spectral_statistics` (`spectral_params`
  itself returns the two values correctly named), so it is legible at the swap site
  rather than hidden.
- **Consumer-facing warning:** `VoiceFeatures.h1h2` therefore holds HRF and
  `VoiceFeatures.hrf` holds H1-H2 — stated in the field docs and the dataclass
  docstring, because a consumer reading `.h1h2` would otherwise get HRF values
  labeled H1-H2 forever, invisibly.
- **Definition sort:** knowable, unambiguous correction — **uncross the two
  assignments** (`h1h2(ig)=h1h2x; hrf(ig)=hrfx`). This is the sharpest feature
  observation: unlike V1 (defensible-intent off-by-one) or V2 (denominator "should
  be a duration"), the fix here is exact and mechanical, the closest a feature entry
  comes to the traceback fix-spec of Reproductions entry 3. Reproduced not corrected
  only because golden parity is the gate and the reference is still developing.
- **Status:** reproduced (feature observation; exact correction known = uncross).

### V4. Harmonic bins read at integer indices despite the `T+2` segment length

- **Where:** `voicekit.features.spectral` (`spectral_params`); the reference
  feature-extraction pipeline, `specParam`.
- **What the reference does:** `oa = abs(fft(useg))/T` is taken over `useg`, which is
  `len(nn) = T+2` samples long (the `T = len(nn)-2` convention — see V1). The
  harmonics are then read at **integer FFT bins** — `oa(2:np+1)` treats bin `k` as
  harmonic `k` (H1 = bin 1, H2 = bin 2), with **no interpolation and no peak search**.
  But the FFT bin spacing is `fs/(T+2)`, while `f0 = fs/T`, so harmonic `k` (at
  `k*fs/T`) actually falls near bin `k*(T+2)/T`, not bin `k` — e.g. `1.0127*k` at
  T=158. The reference reads the integer bin regardless, a small systematic
  under-index of every harmonic.
- **Surfaced by:** the mechanics reading — the synthetic definition-check
  deliberately uses `len(useg)=T` so the bins align and the *formulas* can be
  certified; on real cycles (`len(useg)=T+2`) the bins are the off-by-`2/T` ones.
- **Definition sort:** unexplained, and **kin to V1** — the same `len(nn)-2` period
  convention resurfacing in the harmonic indexing (segment `T+2` long, treated as
  `T`-periodic). Minor (fractions of a bin), reproduced bit-exact. No correction
  specified; a corrected form would interpolate or peak-search near `k*f0`, or take
  the FFT over exactly `T` samples.
- **Status:** reproduced (feature observation, no correction specified).

### V5. Live-IAIF ε propagates into the features (composition precision, not a threshold)

- **Where:** the full-signal composition `iaif → (yaga, derive_flow) → extract_voice_features`,
  at 16 kHz.
- **What it is:** the port's IAIF is a from-scratch reimplementation validated to
  tolerance, so its `residual` matches the captured `udash` only to accumulated,
  BLAS-dependent linear-algebra **ε** (rel ~1e-12; see F1). Running the features from
  that live residual rather than the captured `feat_u`, the ε propagates and — through
  the spectral log/FFT — *amplifies*: measured relative error vs the capture is
  `mfdr`/`pa` ~1e-15, `naq` ~1e-12, and **`h1h2`/`hrf` ~1e-10**. Same-input parity
  (J3/J4, fed the captured residual) stays at ~1e-15; this larger figure is only the
  *from-raw-signal* composition.
- **Why it is here, not a gate:** a fully-live comparison is not a same-input parity
  test, so it must not relax the parity tolerance. The parity gates stay tight
  (J4 asserts the five flow/timing features bitwise, f0/spectral at rtol 1e-12 on
  captured input); the fully-live path is a **runs-and-sane smoke test** (no NaNs, F0
  in range, uniform periods), same category as 8 kHz. These propagation figures are
  recorded so a future reader does not mistake the ~1e-10 spectral spread for a
  regression — it is inherent IAIF ε amplified through the log, not an introduced error.
- **Status:** observation only (no correction; the ε is intrinsic to a tolerance-
  validated IAIF, not a reference oddity).

---

## Step 7 (VUV) — forward findings

Findings surfaced while designing the step-7 voicing milestone (see DESIGN.md §9
item 7). Some are watch-items for the still-unbuilt detector (the decision stage);
others (VUV7 below) are now port-vs-reference reproduction facts, because the
*features* turned out to be golden-masterable — see the scoping fact next.

**Step 7 is capture-and-match for the features, define-the-target for the
decision.** The step-7 fork was originally recorded as "define-the-target" (no
authoritative MATLAB voicing to golden-master), and that is still true of the
**decision** stage: C's GMM and E's trained centroids made it non-deterministic,
and no canonical voicing behaviour exists to match. But the **features**
(the reference VUV feature extractor: Nz, Es, C1, alp1, Ep) are a *deterministic* function of the
signal — no RNG — so they **are** golden-masterable, exactly like steps 1–6. The
features are therefore captured against a MATLAB oracle
(`tests/synthetic/*.vuvfeat.npz`, regenerable via `capture_vuv_features.py`) and
validated bit-exact / machine-ε / BLAS-ε (`test_vuv_features_parity`). This
re-scoping is what made the parity capture possible at all — a later reader
wondering why a "define-the-target" milestone carries a golden-master should read
it as: **features capture-and-match, decision define-the-target.**

### VUV1. The silence pre-gate: design ratified — a finiteness predicate plus a floor guard, never a speech/silence detector

The step-7 output label is binary (voiced / non-voiced), but that is the *output*
domain, not the classifier's internal structure. The pre-gate's design was
**ratified at the decision-rule gate opening (2026-07-16)** as three jobs of
different standing (this rewrite replaces the earlier open-question form of the
entry; the build, and any value, remain at the classifier sub-gate):

- **J1 — remedial: a finiteness predicate, no threshold.** A zero-energy frame
  yields `Es = -inf`, `Ep = NaN`, `C1 = NaN` — dropped-guard artifacts, not
  principled degeneracies (the MATLAB zeroed guards the paper mandates: `eps=0;
  %1e-50` against ε = 10⁻⁵ in Eq. (2) and 10⁻⁶ in Eq. (4); the paper's silent
  frames get a finite floor — VUV10). **`r1` inherits the 0/0 `NaN` too**:
  boundedness does not fix zero energy. J1 needs no calibration at all — it is
  the defined NaN/`-inf` → non-voiced mapping the decision rule must have
  anyway (reachable in practice on *digital* silence: zero-padded or edited
  files). The history-less first frame is already absorbed by the committed
  `start < nar` guard, which is our own principled routing, not the reference's
  dropped one.
- **J2 — principled, and not fully dischargeable by a floor guard.** Near-floor
  *coloured* noise reads **high** on correlation statistics — the paper's own
  Table I silence class measures C1 = 0.649, above its unvoiced class (0.007),
  and D3's aspiration is the in-set analogue (`r1` = +0.271 with zero
  periodicity). So the pre-gate's substantive job is removing frames that would
  otherwise read *voiced*, not "boring" frames. But a floor guard low enough to
  be legitimate (below) cannot catch audible coloured room tone at
  speech-adjacent levels, and no fixed `r1` threshold clears arbitrary colour
  (ρ → 1 for rumble). **The recorded resolution is an operating-envelope
  statement — an architectural limit, stated not hidden:** the fixed threshold
  is calibrated for bounded noise colour, the bound stated, validated at
  Track B, and scored stratified. The **adaptive gate is the named escape
  hatch** if Track B shows the envelope too narrow, with its hazards
  pre-recorded: it breaks per-frame determinism (same frame, different label in
  different files), is undefined on all-silence/all-speech inputs, and absorbs
  the envelope gap instead of stating it (training on the input through the
  back door).
- **J3 — input conditioning (DC/rumble), split out.** J2's physics at 0 Hz;
  paper-mandated fix is *filtering, not gating*; collides with the grid's
  input-neutrality clause. Own entry and own gate: **VUV12**.

**The floor-guard constraint (resolves the old "two-hats" watch item).** The
pre-gate is legitimate **only as a recording-chain floor guard** — a level so
low it can never arbitrate speech content — never a speech/silence detector.
The energy-classifier-in-disguise hazard is real but localized: it lives
entirely in *where the level sits* (threshold creep toward "quiet speech"
levels would eat D1's low-SNR decay frames before `r1` ever sees them — an
energy classifier exactly where D1 probes). A floor guard never decides V vs U
(both members of every energy-matched pair pass it identically), so it does not
touch VUV3's sufficiency-elimination. **Required test when the pre-gate lands
(the anti-creep guard): the pre-gate must never fire on any D1 frame** — D1's
floor is a real noise floor, well above digital zero.

**Threshold provenance (ratified weighting; no value set).** The `r1`
provenance (the textbook `1/√N` null for the bounded Eq. (3) statistic, knob in
`VuvConfig`, never measured off the fixtures) gives the pre-gate nothing; the
pre-gate's own source, per the ratification: **(ii) a physically-motivated
absolute level** (format quantization/dither floor, or a stated dBFS floor) —
out-of-sample by construction, referencing the format and no fixture or corpus
— carries the weight. (iii) A dedicated synthetic calibration construction is
the **check** in derive→predict→check, never the provenance source. (iv)
Adaptive: rejected-for-now, reasons above. (i) The paper has nothing to
transfer — silence there is a *trained centroid* in a 5-D Gaussian, not a
threshold; its only absolute constant, ε = 10⁻⁵ against ±2048 samples
(RMS ≈ 0.003 counts, ~−116 dBFS, below 12-bit quantization noise), is itself a
numerical floor guard — corroborating the floor-guard reading of what an
absolute level can legitimately be. Calibrating an energy level by reference to
D1/D2/D3 remains the floor-fixture-trap circularity in its most direct form
(energy is the feature D1 was constructed to defeat) and stays forbidden.

**Observability is required.** A pre-gated frame is `voiced=False` (coherent
with the binary charter; the domain stays wideable), but the firing must be
observable, for three reasons: (a) Track A/B error analysis must distinguish
"the pre-gate ate it" from "`r1` rejected it," or the pre-gate can silently
consume discriminating regions while aggregate scores stay green (VUV5's
stratification argument, same shape); (b) the anti-creep test above is only
writable if firing is observable — transient ≠ untestable, per the architecture
gate's mask precedent; (c) the observable channel is the seam a later S/U/V
widening plugs into, keeping the widening additive. Field-vs-diagnostic form is
a build-time detail.

- **Status:** design ratified 2026-07-16 (jobs, floor-guard constraint,
  provenance weighting, anti-creep test, observability). Build and value at the
  classifier sub-gate. Cross-ref VUV11 (the D2 limit the same gate ratified),
  VUV12 (J3).

### VUV2. `VoiceFeatures.vuv` renamed to `frame_len_ok` — namespace hazard resolved

`VoiceFeatures.vuv` was the reference's per-cycle **frame-length sanity flag** — a
cycle whose period puts F0 in (40, 400) Hz — faithfully reproduced, **not** a
voicing verdict. Its name invited misreading as a voicing output, a hazard that
would become active once `VoicingTrack.voiced` lands beside it.

- **Resolution:** the field (and `cycle_framework`'s local/return) is renamed to
  **`frame_len_ok`** — named for the predicate it computes (`fs/400 < T < fs/40`),
  so it can never be read as a voicing decision. Pure rename, value and
  computation unchanged; the existing value guards stayed green with only the
  identifier updated (that green is the proof). Done *before* any classifier code,
  so the classifier is written against unambiguous names from its first line.
- **Capture key preserved (a deliberate asymmetry):** the golden `.npz` still
  store this array under `feat_vuv`, which names the **MATLAB reference** variable
  `vuv` (the reference's own name for its 10th output). Only the Python field was
  renamed; the capture key was not, because it documents the reference, not our
  API. The parity assertions (`test_features_framework.py`,
  `test_features_extract.py`) carry an inline note making the `frame_len_ok` ↔
  `feat_vuv` mapping legible so the preserve-not-rename asymmetry is not mistaken
  for stale drift. (cf. V3 for another reproduced naming oddity in the same
  feature reference.)
- **Status:** resolved. (`VoicingTrack.voiced` itself is still unbuilt — it
  arrives with the classifier.)

### VUV3. Discriminating fixtures prove *sufficiency-elimination* only, never necessity

The three discriminating fixtures (D1/D2/D3, `tests/synthetic/`) are built so that
**periodicity is the sole surviving separator**: each defeats one or more
non-periodicity features (D1 energy asymptotically; D2 energy exactly + most of
zero-crossings; D3 energy exactly + spectral tilt), while the matched-pair / taper
devices decorrelate every non-periodicity feature from the label. The surviving
separator is genuine F0 periodicity (autocorrelation at the pitch lag, not lag-1
smoothness — verified so a low-tilt breathy region cannot pass on smoothness).

- **What the set proves:** no non-periodicity feature (energy, zero-crossings,
  tilt) is **sufficient** for the label — there exist equal-value, opposite-label
  frames for each.
- **One precise bound — D2 zero-crossings are defeated only to ~3%, not exactly.**
  The matched pair (shared turbulence) makes energy *exactly* equal, but
  superimposing the periodic source lowers the voiced region's zero-crossing rate
  by a bounded ~3% (measured ratio ≈ 0.97). This is intrinsic to adding a
  low-frequency periodic component onto turbulence, not a seed-slice artifact (the
  two regions share one turbulence realization). Sufficiency is still eliminated
  because the per-frame ZCR distributions overlap — no single frame's ZCR decides
  the label — but "ZCR provably equal" would overclaim; the fixture test asserts
  the bounded leak (`0.95 < ratio < 1.0`), not equality.
- **What it cannot prove:** that any feature (periodicity included) is
  **necessary**. Testing necessity would need a case where periodicity is *also*
  defeated yet the label stays determinable by another route; by construction no
  such case exists (periodicity is the only thing left tracking the label).
- **What ratifying therefore licenses the classifier gate to claim:** only the
  negative — "the classifier may not rely solely on energy / zero-crossings /
  tilt." It does **not** license "must use periodicity" or "periodicity suffices."
- **Status:** scope boundary; carry into the classifier sub-gate. See DESIGN.md §9
  item 7.

### VUV4. Per-fixture realism gaps — the discriminating set is optimistic for periodicity

The construction guarantees the *label* is feature-free, but not that the fixtures
are as hard as reality *for the periodicity features* the set rewards.

- **Gaps baked in:** D2/D3 model voiced frication / breathy voice as **additive,
  independent** source + turbulence with the source's periodicity **unmodified**;
  D3's source is **jitter/shimmer-free**. Real voiced fricatives modulate
  turbulence pitch-synchronously and can have irregular voicing; real breathy
  voice has cycle jitter — both further depress the periodicity a detector would
  measure. So `C1`/`Ep` likely succeed *more easily* here than on real signals.
- **Named hardening knobs (deferred worklist):** pitch-synchronous turbulence
  modulation (D2); cycle jitter/shimmer (D3). Adding either is a new fixture
  variant, not a change to these.
- **Consequence for the pitch-lag assertion when jitter is added.** The D2/D3
  tests assert periodicity at a **single, fixed** pitch lag (`round(fs/f0)`) —
  valid because the current sources are exactly periodic, so all energy sits in
  one bin. Turning the jitter knob spreads the pitch peak across a *band* of lags,
  so the fixed-bin autocorrelation drops even though genuine periodicity is still
  present. A later chat adding jitter must therefore widen that assertion to a
  **lag-band search** (max autocorrelation over `fs/f0_max … fs/f0_min`, the form
  already used in the probes) — a falling fixed-bin value is the *expected*
  consequence of the knob, **not** a broken fixture. Widen the assertion; do not
  read its failure as a regression.
- **Status:** open worklist for a harder fixture iteration, co-designed with the
  classifier. See DESIGN.md §9 item 7.

### VUV5. D1's energy-defeat is asymptotic-in-the-tail, not a matched-pair contrast

Unlike D2/D3 (where the energy-matched pair makes energy equal *pointwise*), D1's
energy-defeat holds **only in the decay tail**, where voiced-frame energy
asymptotically approaches the floor. Over the whole fixture energy correlates with
the label (high-energy onset, low-energy floor); it fails only in the sub-floor
tail.

- **Consequence:** D1's energy-defeat is provable **only under SNR-stratified
  scoring** — evaluating the low-SNR tail frames specifically. An energy detector
  scores well on D1 *in aggregate* (onset + floor right, tail wrong), so an
  aggregate metric hides the discriminating frames.
- **Mitigation shipped:** D1 exports its per-region SNR (`region_hard_param`,
  `hard_param_name == "snr_db"`) as the stratification channel so a later scorer
  can bin by difficulty. (D2 exports VFR, D3 exports HNR, for the same reason.)
- **Status:** a requirement on the (deferred) scorer, not on the fixture. See
  DESIGN.md §9 item 7.

### VUV6. VUV frame grid locked: 32 ms / 10 ms, its own config, independent of IAIF

The voicing frame grid is locked at **32 ms frames / 10 ms hop** (the reference
the reference VUV feature extractor's defaults), in `VoicingGrid` (`src/voicekit/vuv/grid.py`) — its own
config, **not** derived from `IaifConfig`. @16 kHz: `frame_len` 512, `hop` 160,
guard band **W = 512/2 + 160/2 = 336** samples; @8 kHz: 256 / 80 / 168.

- **Attribution corrected (2026-07-16, with VUV10):** this entry originally called
  32/10 "the Atal-Rabiner voicing-analysis standard." The paper (read in full for
  VUV10) uses **10 ms non-overlapping blocks** (N=100 @ 10 kHz; "segments as short
  as 10 ms" is the abstract's selling point). The 10 ms *hop* matches the paper's
  block rate; the **32 ms window is the MATLAB's own convention**, 3.2× the
  paper's, and is not in the paper. The grid stays locked at 32/10 — its rationale
  (sized for voicing, independent of IAIF, hop settled by the LPC-source question
  below) is unaffected; only the provenance claim was wrong.

- **Why its own config (the hop was the live decision).** `VoicingGrid` and
  `IaifConfig` share a 32 ms frame length by **coincidence**; they differ on hop
  (10 vs IAIF's 16 ms) and serve different purposes (voicing vs inverse filtering).
  The hop was settled by the LPC-source question: the Atal-Rabiner LPC-derived
  features (**`alp1`, `Ep`** — *not* `C1`, which is direct unit-lag autocorrelation
  off the frame) recompute **covariance** LPC at order 16 on the **raw input** at
  VUV timing, so they do **not** read IAIF's per-frame LPC output (different method,
  order 20/4/20, pre-emphasised signal, 32/16 grid). The grids are therefore
  independent and the hop is sized for voicing. A "DRY the two 32 ms constants"
  refactor must not couple them — `test_vuv_grid` enforces this structurally.
- **Projection pinned.** Nearest-centre, `round((s-(frame_len-1)/2)/hop)`, is the
  single source in `VoicingGrid.project` for the derived mask's GCI→frame lookup.
- **Input-neutrality (ratified) + resample clause.** The grid is applied at the
  signal's own fs with **no internal resample**, so the frame centres are identical
  whatever signal is framed (raw/residual/flow) and locking the grid commits none
  of the open input leans. A later classifier-design choice to resample to a fixed
  internal rate would **re-open** grid neutrality and must be co-decided then.
- **Status:** grid locked and single-sourced; W numeric; projection pinned. The
  threshold, feature set, and track/detector logic remain at the sub-gate.

### VUV7. C1 is doubly load-bearing — a single point of failure the fixture cannot catch

`C1` (`vuv/features.py`) is simultaneously the **sole** floor separator — it alone
separates the D2/D3 RMS-matched pairs (`Ep` **inverts** on D2: order-16 LPC models
the peaky frication noise more efficiently than the broadband voiced mix, ~+2.97 V
vs +5.84 N; `alp1` tracks tilt, decoupled from voicing by D3; `Nz` only ~3%), so
the fixture's whole energy-only-rejection verdict rests on it — **and** the feature
the decision-rule noise-null threshold will apply to. The roles are coupled: a bug
in C1's reproduction collapses both, and the floor **cannot** catch it, because the
floor assertion *is* "C1 separates" — a wrong C1 that still separates passes.

- **Reproduce-the-definition payload — a numerator/denominator `s0` asymmetry
  (surfaced quirk, reproduced not corrected).** The reference line is
  `sum(s(2:end).*s(1:end-1)+s(1)*s0) / sqrt(ssq*([s0; s(1:end-1)]'*[s0; s(1:end-1)]))`
  (the reference VUV feature extractor's C1 line). By MATLAB semantics
  (`s` is `N×1` since `sp=sp(:)`; `s(1)*s0` is a **scalar**; `(N-1)×1 vector +
  scalar` broadcasts the scalar), the **numerator** boundary term `s(1)*s0` enters
  **N-1 times**: `Σ(s(2:end).*s(1:end-1)) + (N-1)·s(1)·s0`. The **denominator**'s
  `[s0; s(1:end-1)]` is an `N×1` vector with `s0` as **one element**, so its `s0`
  enters **once**. That numerator-broadcast/denominator-once asymmetry breaks
  Cauchy-Schwarz and is exactly why C1 is **unbounded above** (>1; 1.448 measured
  on D3). The intent is no longer an inference (2026-07-16, VUV10): **Atal &
  Rabiner (1976) Eq. (3) — which the MATLAB's header cites as its definition —
  adds the boundary term once**; the MATLAB's denominator implements Eq. (3)
  term-for-term and its numerator differs by a single misplaced parenthesis
  (`sum(v + s(1)*s0)` for `sum(v) + s(1)*s0`). A genuine formula bug, established
  from the primary source (see [docs/vuv_c1_decision.md](docs/vuv_c1_decision.md)
  §Q2). The code broadcasts — reproduced faithfully (the parity capture matches
  MATLAB only if we broadcast), **not corrected to add-once**. The floor verdict
  (C1 separates) holds under *either* reading; only the unboundedness (and thus
  VUV8) depends on the broadcast.
- **Mitigation (landed):** C1's fidelity gets the strongest verification of the
  five — hand-computed synthetic-known-value tests isolating the `s0` reach, the
  broadcast, the denominator (`tests/test_vuv_features.py`), **and** the
  reference VUV feature extractor parity capture (`tests/test_vuv_features_parity.py`, oracle
  `tests/synthetic/*.vuvfeat.npz`).
- **What the parity capture proved (VUV7 closed):**
  - **C1's broadcast reading is confirmed BIT-EXACT by the oracle** (0.0 abs error
    on all four fixtures). The reproduced numerator/denominator `s0` asymmetry is
    what MATLAB computes; a wrong-but-separating C1 — the hole the floor cannot
    cover — is now caught by parity.
  - **The capture caught the `alp1`/`Ep` DC-offset gap the synthetic tests
    structurally could not.** Commit 2 read `alp1`/`Ep` from plain covariance LPC;
    the oracle showed them off by ~1.3e-2 / ~5.7e-2, tracing to the reference VUV feature extractor's
    three-output `[ar,e,dc]=lpccovar` (DC-offset fit). Routing through
    `dc_offset=True` (commit 3b) brought them to BLAS-ε (≤3.4e-12 / ≤3.8e-8). This
    is the concrete evidence the capture was **required**, not optional: the
    synthetic tests never compared `alp1`/`Ep` to the reference, so only parity
    could find it.
- **Status:** **CLOSED.** C1 still gets the most scrutiny wherever touched; VUV8
  (below) remains open and independent.

### VUV8. Reference-C1 null derived — a normal-product (not 1/√N), and C1 is per-frame-unviable

The ratified provenance (VUV1) was "autocorrelation std ≈ 1/√N over an aperiodic
frame" — the **textbook bounded** autocorrelation's null. The reference C1, via the
numerator-broadcast/denominator-once `s0` asymmetry (VUV7), is unbounded, so 1/√N
does not apply. **The null is now derived analytically for the actual formula —
full derivation and predictions in [docs/vuv8_c1_null.md](docs/vuv8_c1_null.md).**

- **The null is a normal-product, not a correlation statistic.** The broadcast
  boundary term `B = (N-1)·s[0]·s0` carries **~99.8%** of the numerator variance
  (std `N-1 ≈ 511` vs the lag-1 sum's std `√(N-1) ≈ 22.6`; the full `Var[P]=N-1`
  sum is in the doc), so under the null `C1 ≈ s[0]·s0` — the product of two
  boundary samples, density `K_0(|z|)/π`. `E[C1]=0`; **`std[C1] ≈ 1`
  (≈√((N-1)/N)), essentially N-independent** — larger than the textbook `1/√N ≈
  0.044` by `√N ≈ 22.6`. A textbook-null threshold (~0.073) vs the correct one
  (~1.7) differ by **~23×**; the wrong one passes nearly every noise frame as
  voiced. That factor is why the item was blocking.
- **Coloured-noise honesty:** real fixture noise is coloured (`s0` adjacent to
  `s[0]`), giving `E[C1] ≈ 2ρ` — the white null is **optimistic** (threshold too
  low → false positives) for positively-correlated noise, conservative for
  high-pass (D2). The white null cannot be assumed safe; a coloured null needs ρ.
- **Per-frame unviability (a FINDING, not a caveat):** the null's O(1) spread is a
  **single boundary product**, not an average, so it does **not concentrate with
  N** — `std ≈ 1` at any frame length, while voiced sits at `2ρ_v ≈ 1.4`; the two
  overlap heavily frame-by-frame. No threshold fixes this — it is a property of
  the *statistic*, not of where the threshold sits. **This rests on the
  derivation alone.** A claimed independent corroboration — that the reference's
  decision stage applied `medfilt1` to `C1`, so "it knew, and smoothed" — was
  **false and is withdrawn** (from source, 2026-07-17; VUV15): the reference's
  only `medfilt1` is a 3-frame median on the **label sequence**, the paper's
  3-level contour smoothing as post-processing of a decision. **Nothing in the
  reference smooths `C1`.** The finding is unaffected (a derivation is not
  evidence); the corrected story is stronger — the author never noticed the
  broadcast's consequence, which is what a silent one-parenthesis vectorization
  error looks like from the inside (VUV7/VUV10).
- **This hands the decision-rule gate its OPENING QUESTION** (structural — it must
  **not** be absorbed into a threshold choice): (a) **smooth C1 across frames**
  (keeps the golden-mastered formula, but the decision stops being per-frame and
  the smoothing window needs its **own** out-of-sample provenance, un-fittable to
  D1/D2/D3 — this option was real, but its "the reference did it" pedigree was
  invented, see above); or (b) **use the add-once C1** (bounded,
  concentrates as `1/√N`, per-frame threshold viable — but it **corrects a
  reproduced quirk**, diverging from the golden-mastered feature layer, so it needs
  a **named quarantine flag and its own ledger entry** per reproduce-and-quarantine).
- **The trap (unchanged):** with 1/√N invalid, the pressure is to *measure* C1 on
  D2/D3's noise regions — fitting-to-the-fixture. Out-of-sample survives only
  because the null is derived analytically (done); the fixture is used only to
  **check** the prediction (doc item 4), never to fit.
- **Status (updated 2026-07-16): derivation discharged; check done; fork resolved.**
  (i) The fixture **check** of the doc's item-4 prediction is done: re-measured on
  D2/D3 (dense slide over the region interiors, n=237/region, N=512),
  `E[C1] ≈ 2ρ` confirmed on all three region pairs — D3 aspiration +0.588 vs
  2×0.271, D3 breathy +1.305 vs 2×0.625, D2 frication −0.377 vs 2×(−0.159),
  including the predicted cross-fixture sign flip — with std O(1) (0.96–1.10),
  non-concentrating. (ii) The per-frame **fork** is resolved and recorded in
  **[docs/vuv_c1_decision.md](docs/vuv_c1_decision.md)** — the decision record
  that pairs with the derivation ([docs/vuv8_c1_null.md](docs/vuv8_c1_null.md);
  math there, reasoning there-not-here): broadcast `C1` stays the golden-mastered
  feature-layer output, unchanged, no flag; the **decision layer** (define-the-
  target, no reference decision stage to depart from) gets its **own named
  statistic `r1`** = Atal & Rabiner (1976) Eq. (3) — established by VUV10 as the
  paper's formula, not a "corrected C1" — so neither fork option (a) smoothing
  nor (b) flag-quarantined correction is taken; the fork's premise (that the
  decision must consume the reproduced feature or a corrected version of it)
  dissolved on the primary-source reading. Option (a) is additionally foreclosed
  by measurement: the required smoothing window (330–750 ms at z=2–3) is 16–36×
  the guard band W and longer than D1's entire 370 ms structure. Still no
  threshold value — that, and `r1`'s implementation, belong to the decision-rule
  gate. Cross-ref VUV7 (same feature), VUV10 (paper fidelity).

### VUV9. Coverage gap: no fixture exercises a rate where reference `ceil` ≠ VoicingGrid `round`

the reference VUV feature extractor frames with `ceil(dur·fs)`; the locked `VoicingGrid` uses `round`.
They **coincide at 8 kHz and 16 kHz** (exact products), which is every current
fixture — so `round` wins with no conflict, and reference-`ceil` is reproduced
where coincident. But no fixture exercises a rate where `ceil ≠ round`, so that
divergence is **tracked, not assumed**. If such a rate is ever added, the feature
framing (`VoicingGrid.round`) and the reference (`ceil`) will diverge by a sample
and must be reconciled. Coverage-gap-style item, VUV-local. Status: open gap.

### VUV10. Paper fidelity characterized: the reference is a loose implementation of Atal & Rabiner 1976

The primary source (Atal & Rabiner, *IEEE Trans. ASSP-24*(3), 1976, pp. 201–212;
full reprint from Rabiner's UCSB archive) was read in full on 2026-07-16 to
establish what the reference VUV feature extractor — whose header cites the paper
as the definition of its five features — was *trying* to compute. Finding: **the
MATLAB is a loose implementation of the paper generally, with C1's broadcast the
only outright formula error.** Our golden master proves parity with the MATLAB;
it is silent on fidelity to the paper. That gap is now characterized rather than
unknown:

- **C1 (the one formula bug):** the paper's Eq. (3) enters the boundary term
  `s(1)·s(0)` once (and states C1 "by definition, varies between −1 and +1");
  the MATLAB numerator broadcasts it N−1 times via one misplaced parenthesis
  while its denominator implements Eq. (3) term-for-term. See VUV7 (reproduced),
  VUV8 (consequences), [docs/vuv_c1_decision.md](docs/vuv_c1_decision.md)
  (decision).
- **Guards dropped:** the paper mandates ε = 10⁻⁵ inside `Es` (Eq. (2), against
  ±2048 12-bit samples) and 10⁻⁶ inside `Ep` (Eq. (4)); the MATLAB deliberately
  zeroes them (`eps=0; %1e-50`, its own "avoid taking logarithm of zeros"
  comment left standing). The reproduced `-inf`/`NaN` silent-frame values are
  therefore a *departure from the paper*, not a principled reference degeneracy
  — restated at VUV1 (the pre-gate compensates for a dropped guard).
- **Preprocessing disabled, DC handled differently:** the paper's front end is
  4 kHz LPF → 10 kHz/12-bit → its Eq. (1) 200 Hz two-pole/two-zero high-pass
  (a=130·2π, b=200·2π) — DC/hum removal *before* analysis, so its LPC has no DC
  term. The MATLAB **transcribed exactly that Eq. (1) filter (lines 61–63) and
  commented it out**, and instead calls the three-output `[ar,e,dc]=lpccovar`
  (DC-offset fit). So the reference's `dc_offset` LPC is evidently a
  *substitute for the removed preprocessing*, not an arbitrary quirk — the
  finding that explains why routing `alp1`/`Ep` through `dc_offset=True`
  (commit 95cb4dd) was required for parity. *(The transcription's LPF line
  carries a latent bug — `butter(4,4000/par.fs)` normalizes by `fs` where
  MATLAB wants Nyquist, giving a 2 kHz cutoff at 10 kHz rather than the paper's
  4 kHz. It is commented out and never ran, and the anti-alias LPF is not ours
  to reproduce; noted so it is not rediscovered as a finding.)* The Eq. (1)
  transcription itself is **correct and is the established generalization** to
  arbitrary `fs`: `T → 1/fs` with `a`, `b` fixed in rad/s — the paper's
  `T = 10⁻⁴` is exactly the sampling period at its own 10 kHz. See VUV12.
- **Order changed:** the paper says p = 12 "typically"; the MATLAB takes the
  order from its caller and our config uses 16. "The Atal-Rabiner default 16"
  attribution previously in `features.py` was wrong and is corrected (16 is the
  MATLAB caller's convention). Value unchanged — parity binds.
- **Framing changed:** the paper uses 10 ms non-overlapping blocks (N=100
  @ 10 kHz); the MATLAB defaults to 32 ms / 10 ms. VUV6's attribution corrected
  in place.
- **Decision architecture (context for the classifier gate):** the paper never
  thresholds a feature — it runs a 5-D Gaussian minimum-distance rule with full
  class covariances, trained per recording condition (~6 s × 4 speakers), and
  its Table I silence class measures **C1 = 0.649 ± 0.158** (above unvoiced at
  0.007): the coloured-noise floor, in the paper's own 1976 data, absorbed by
  training. See [docs/vuv_c1_decision.md](docs/vuv_c1_decision.md) §Q3 for why
  that architecture made lag-1 survivable and a fixed-threshold rule has no
  equivalent absorber.
- **Status:** characterization, not correction. Parity with the MATLAB remains
  the feature-layer gate; no reproduced value changes. Paper-vs-MATLAB
  divergences are candidates only insofar as a *decision-layer* design chooses
  the paper's form (as `r1` does for Eq. (3)); the feature layer never diverges.

### VUV11. D2 is a bounded limit of the fixed-threshold architecture (C′) — "the other four" closed by set-level straddling, not per-pair weakness

Ratified at the decision-rule gate opening (2026-07-16). The question "what
carries D2?" was answered by measurement (dense slide, stride 8, n=237/region,
locked grid N=512 — the same protocol as the C1 re-measurement), and the answer
reframed the options.

- **Per-pair, the other four are NOT dead on D2** — the expectation "probably
  no" was wrong: on D2's matched pair, **`Ep` separates at 10.7 σ** (V +3.20 ±
  0.18 vs N +7.13 ± 0.19) and **`alp1` at 7.0 σ** (V −0.079 ± 0.073 vs N +0.858
  ± 0.061); `Nz` 0.4 σ (the ledgered ~3% leak), `Es` 0.0 σ (matched by
  construction). The separating cue is the added low-frequency source energy
  changing spectral balance at exactly matched total energy — **the voice bar,
  which is genuine acoustics** (a documented phonetic cue for voiced
  fricatives), not a pure construction artifact.
- **What closes the "other four carry it" route is set-level straddling:**
  across D2+D3, every feature's *voiced class spans its non-voiced values*, so
  no fixed single-feature threshold produces the label —
  `Ep`: voiced spans +3.2 … +54.2 with non-voiced (+5.3, +7.1) *inside*, and
  the direction **flips between fixtures** (voiced is low-`Ep` on D2, high-`Ep`
  on D3); `alp1`: voiced spans −5.33 … −0.08 with D3's aspiration (−1.30) *more
  negative than* D2's voiced fricative; `Nz`: voiced spans 28.7 … 265.9 with
  non-voiced (209.9, 273.2) inside; `r1` likewise (next bullet). The fixtures
  eliminate sufficiency not by nulling features per-pair but by making the
  voiced class straddle the non-voiced values. Closed by measurement, not
  presumption.
- **The closing arithmetic for the chosen architecture:** any `r1` threshold
  that clears D3's aspiration (+0.271) necessarily rejects D2's voiced
  fricative (−0.055) — D2's voiced member sits *below a non-voiced region of
  the same set* on the decision statistic. **Fixed-threshold `r1` therefore
  systematically labels D2's voiced frication non-voiced.** For the correlation
  family generally, D2's gap-to-noise is construction-fixed and the per-frame
  spread is `1/√N` estimation noise: 1.0 σ → 3 σ needs ~9× the frame length
  (~290 ms) — resolution death. The pitch-lag route does not rescue D2 either
  (+0.068 vs −0.020, measured).
- **The 1976 insight:** the four features are individually incoherent across
  conditions yet **jointly separable** (Mahalanobis distance between class
  means under pooled covariance: 28.4 on D2's pair, 14.1 on D3's) — our own
  measurement reproduces, with the 1976 feature set, the design pressure that
  made Atal & Rabiner **train a full-covariance Gaussian rather than
  threshold** (VUV10, Table I). We rejected their remedy for named
  licensing/generalization reasons; this is what the remedy was for.
- **C′, precisely bounded:** D2 is a limit **of the chosen architecture** (a
  fixed threshold on a single periodicity statistic), *not* of per-frame
  detection in general — the per-pair separations above prove the information
  is present. Known, stated, VFR-stratified, inside VUV3's ratified scope (the
  set eliminates sufficiency; it never promised the hard cases are solvable).
- **Falsifier (where the evidence would come from):** Track B corpus
  evaluation — real voiced fricatives at VFR ≤ 0 dB reliably detected against
  EGG ground truth would show the limit was architectural complacency, not a
  bound. The realism gap cuts **both ways** (VUV4): D2's additive-independence
  construction likely *overstates* the waveform voice-bar cue (real weak
  voicing = weak voice bar; `alp1`/`Ep`'s 7–10 σ may not survive realism) and
  *understates* envelope cues (real turbulence is pitch-synchronously
  modulated — an envelope-periodicity feature would have a signature D2-as-
  built lacks entirely; VUV4's hardening knob would add it). Both "spectral
  shape carries real D2" and "nothing carries real D2" are fixture-external
  empirical claims.
- **Three forward requirements (the guards that keep C′ a stated limit, not
  complacency):** (1) the scorer **must stratify by VFR** — D2's aggregate
  score would hide the limit; this is what the fixture's metadata channel was
  shipped for (VUV5); (2) when the classifier lands, the D2 limit gets its own
  ledger entry — a documented property, not a discovered surprise; (3) any
  future joint/spectral-shape route needs a **named out-of-sample
  justification** (the voice bar is documented in the phonetics literature,
  independent of D2) plus **corpus-driven — never fixture-driven — structure**.
- **Status:** framing ratified (C′). The three requirements bind the scorer,
  the classifier build, and any future feature-set expansion. Cross-ref VUV1
  (same gate), VUV3/VUV4/VUV5 (scope, realism, stratification), VUV10 (the
  trained-Gaussian context), docs/vuv_c1_decision.md (r1 and the D2 numbers it
  already records).

### VUV12. Input conditioning for `r1` (DC/hum/rumble): P3 with enforcement — precondition + helper + violation check; gate closed

Surfaced at the decision-rule gate opening (2026-07-16); **closed at its own
gate (2026-07-17)**. This rewrite replaces the open-question form of the entry;
the ratified decision is the entry. Background (unchanged): the paper
high-passes at 200 Hz (its Eq. (1) two-pole/two-zero filter) **before all five
features**; the MATLAB dropped that preprocessing and compensated only
`alp1`/`Ep` via the DC-offset covariance LPC (VUV10) — so `C1`/`r1` read a
**raw** frame, and a DC offset or sub-speech-band energy drives `r1` → 1 (DC is
the limit case of low-pass colour — the silence pre-gate's J2 problem at 0 Hz,
VUV1).

- **The hum fact — the physical reason conditioning is mandatory, not
  paper-deference.** Mains hum is not colour, it is a **periodicity impostor**:
  a 50 Hz hum at 16 kHz has lag-1 correlation cos(2π·50/16000) ≈ 0.9998 *and is
  genuinely periodic*, so it defeats any threshold on any correlation statistic
  **forever** — thresholds defend against noise, not against actual
  periodicity. Once hum is in the frame it is undetectable downstream by
  construction: `r1` cannot distinguish it from voicing even in principle. The
  defense can only live at the input boundary — which is what promotes the
  violation check below from optional to **load-bearing**.
- **The decision: P3 with enforcement.** (1) A **documented precondition** on
  `voicekit.vuv`: input DC-free and free of sub-speech-band energy. (2) An
  **explicit conditioning helper owned by `voicekit.vuv`** (the consumer that
  needs it — provenance kept local, matching the corpus-adapter pattern),
  shipping the paper's Eq. (1) as its default, paper-cited, with the
  cutoff-vs-F0 reasoning documented (below). (3) A **detectable-violation check
  inside the detector** that *reads, never rewrites* its input — warning or
  raising on DC/sub-band content. Analysis-without-modification keeps the
  input-neutrality clause's letter *and* spirit (VUV6): the detector still sees
  exactly what the caller passed; it merely refuses to answer confidently on
  input it cannot answer correctly.
- **Why P1 (detector-internal filtering) was rejected — in the terms that
  decided it, not "internal filters are untidy."** P1's filter would sit above
  the `frame_features_at` seam, so *formula* parity would survive — but it
  would **permanently kill composed-path oracle-comparability**: the MATLAB
  never filters, so no capture of a filtered path can exist, ever. It would be
  the project's **first out-of-oracle transformation** — everything voicekit
  does to a signal today (IAIF's filtering, YAGA's transforms) lives *inside*
  the oracle's own path — dragging part of the feature path from
  capture-and-match into define-the-target, which the fork-scoping (VUV7)
  ratified for the *decision layer only*. P2 (automatic at I/O) is foreclosed
  outright: every golden capture in the project was made on raw fixture
  signals, and DESIGN §3's own precedent names the sin — explicit selection,
  **never a silent downmix**; silent filtering is the same sin in the frequency
  domain.
- **Eq. (1)'s provenance — and its bound.** The paper's features are *defined
  on the conditioned chain*: Fig. 1's order is scale → HPF → block →
  measurements, so Table I's class means (silence C1 = 0.649, voiced 0.881)
  were measured **post-HPF**. Eq. (1) is part of the feature definitions'
  source, not an external choice, and is transferable (the MATLAB's own
  commented-out transcription already generalized its coefficients to arbitrary
  fs). The cutoff-vs-F0 worry resolves: Eq. (1) is a second-order section with
  a double zero at DC and a resonance-shaped corner near 200 Hz — it
  *attenuates* a low fundamental, not annihilates it; and `r1` does not need
  the fundamental anyway (voiced high-`r1` comes from spectral tilt carried
  through harmonics and formants above 200 Hz — Table I's voiced 0.881 was
  measured with the HPF in the chain, on a corpus including male speakers).
  **The bound, stated so nobody reads this gate as narrowing VUV1:** the 1976
  silence class read C1 = 0.649 *after* high-passing — conditioning discharges
  **J3 only** (caps the divergence at the 0 Hz end: DC, hum, rumble); J2's
  mid-band colour and VUV1's operating-envelope statement stand **fully
  unchanged**.
- **The DC-vs-rumble split.** Per-frame mean removal inside
  `frame_features_at` is **foreclosed outright** — it would change the
  golden-mastered formulas themselves; parity dies at the *formula* seam, not
  just the composed path. Signal-level mean removal is parameter-free but fixes
  only constant offset (not drift, not hum), so it does **not** discharge
  VUV12. Rumble/hum needs a real corner, hence a parameter, hence the
  provenance above. The DC violation check is nearly parameter-free
  (mean-to-RMS ratio, generous margin); the sub-band check needs the same band
  a filter would.
- **The named cost, not softened.** P3 buys parity (both senses: formulas
  reproduce the oracle *and* the composed path stays oracle-comparable) and
  neutrality, at the price of a **contract someone must uphold**: a warn-only
  check can be ignored; whether real corpora arrive conditioned (or the helper
  gets used) is untested until Track B; and the check's band needs the same
  provenance a filter would — P3 *relocates* the parameter question rather than
  dodging it, to a place where being wrong is **noisy** (a missing or spurious
  warning) instead of **silently mislabeled** (wrong, confident, quiet).
- **Two forward requirements.** (1) A DC/hum fixture must be built — nothing
  currently exercises the hazard (every committed fixture is zero-mean by
  construction); derive → predict → check once the helper/check land, never
  before. (2) If the pitch-lag route (decision-doc further research) advances,
  the conditioning corner and the lag band must be **reasoned jointly** — a
  200 Hz HPF and a low-F0 lag search interact.
- **Status:** placement ratified (P3 with enforcement) 2026-07-17. Helper,
  check, and their parameters (with the provenance constraints above) belong to
  the build; no filter implemented, no value set. Cross-ref VUV1 (J2/J3
  standing), VUV6 (input neutrality), VUV7 (fork-scoping), VUV10 (the dropped
  front end).

### VUV13. Strong aspiration is a bounded limit of any fixed lag-1 threshold — the voiceless-vowel physics (kin to VUV11)

Ratified at the ρ_env gate (2026-07-17), from the literature search that gate
commissioned. This is the more fundamental of the two ledgered limits, because
it is physics, not fixture construction:

- **The mechanism.** Aspiration ([h], the aspirated interval of stops) is
  **acoustically a voiceless vowel**: a glottal turbulence source — per Klatt
  (1980, p. 7), the synthesis-standard turbulence source is broadband through
  a −6 dB/octave low-pass, only ~6 dB/oct flatter than the voicing source —
  filtered by the **full vocal tract**, so its spectral envelope is the
  co-articulated vowel's envelope with a noise excitation. Since lag-1
  correlation is determined by the spectrum, **aspiration's ρ approaches the
  vowel's own ρ. No fixed lag-1 threshold at any α excludes it, ever** — the
  same shape as the hum finding (VUV12), one level up: not an impostor by
  periodicity, but by spectral envelope. D3's aspiration (band-limited
  300–6000 Hz, ρ = 0.271) is a **mild instance**; real strong aspiration sits
  higher. Corroborations in data that predate our fixtures: Table I's
  unvoiced class reaches +2σ ≈ 0.71 (its upper tail is this material) and its
  booth silence — low-pass coloured, the environmental cousin — reads 0.649.
- **The limit, in VUV11's shape:** stated (a fixed-threshold `r1` rule labels
  strongly-aspirated non-voiced frames voiced), stratified (D3's `hnr_db`
  channel is the fixture-side instrument; corpus scoring must report
  aspirated segments separately), Track-B-falsifiable (real [h]/aspirated-stop
  segments against EGG ground truth measure where real aspiration actually
  sits; consistently low measured ρ would show the voiceless-vowel concern
  overstated for real corpora — the falsifier runs in the opposite direction
  from VUV11's).
- **Consequence for ρ_env** (see [docs/vuv_rho_env.md](docs/vuv_rho_env.md)):
  Table I's unvoiced class *bundles* this excluded material in its upper
  tail, so a margin constructed to cover the full class double-counts this
  limit into the threshold — the mechanism behind the derivation's
  under-determination finding.
- **The forcing function it hands the pitch-lag route.** Aspiration has the
  vowel's *envelope* but **no peak at the pitch lag** (D3 measured: breathy
  voiced +0.482 vs aspiration +0.013 at lag 89) — the pitch-lag statistic
  dissolves this limit outright. That is now **two independent limits (D2 /
  VUV11, aspiration / VUV13) pointing at the same escape**, which sits in
  docs/vuv_c1_decision.md §Further research behind the F0-circularity open
  question.
- **Status:** ledgered limit of the fixed lag-1 architecture; binds the
  scorer (aspiration-stratified reporting) and any ρ_env declaration (the
  exclusion must be named in its rationale, per the derivation doc). Cross-ref
  VUV11 (the sibling limit), VUV12 (the hum kin), VUV14 (the convergence),
  docs/vuv_rho_env.md.

### VUV14. The convergence: lag-1 is established wrong-for-this-job from three independent directions, and its successor is identified

Recorded at the ρ_env gate (2026-07-17). VUV11, VUV13 and the ρ_env
declaration each arrived at a limit of the fixed lag-1 architecture, and
filing them as three separate caveats **understates what they are jointly**.
Their independence is the point — they come from different evidence classes
and could not have contaminated one another:

1. **Fixture-constructed (VUV11).** D2's voiced frication at VFR ≈ 0 dB: no
   lag-1 statistic separates the matched pair per-frame (~1.0 σ; `r1` voiced
   −0.055 ± 0.052 vs unvoiced −0.159 ± 0.049), and any `r1` threshold clearing
   D3's aspiration necessarily rejects it.
2. **Physics/literature (VUV13).** Aspiration is acoustically a voiceless
   vowel (Klatt's turbulence source only ~6 dB/oct flatter than voicing,
   full-tract filtered), so its ρ approaches the co-articulated vowel's: **no
   fixed lag-1 threshold excludes strong aspiration at any α, ever.** Nothing
   fixture-derived; it would hold if D1–D3 had never been built.
3. **The source paper's own real-speech measurements (docs/vuv_rho_env.md).**
   Table I's classes overlap at 2σ *in this exact statistic* — unvoiced +2σ
   (colour) ≈ 0.71 against voiced −2σ ≈ 0.73 — so a 1-D lag-1 margin carries
   **~2% error on each side on 1976's easy material** (booth, read speech, four
   speakers) *before* any hard case. Measured in 1976, five decades before our
   fixtures existed. Sharper still: the ρ_env evidence **cannot determine
   whether a by-construction-voiced region is inside the envelope at all** —
   the admitted margin range (0.53–0.81 at 16 kHz) straddles D3's breathy
   voice, which survives only at the range's floor. When the evidence cannot
   place a clearly-voiced signal on the voiced side, the statistic is not
   merely imprecise for the job.

**The finding.** Three independent lines — one constructed, one physical, one
historical-empirical — converge on the same conclusion: lag-1 correlation is
not *suboptimal* for voicing detection, it is **wrong for this job**, and the
1976 system's five-dimensional trained classifier was the remedy for exactly
this (VUV10, VUV11's Mahalanobis finding). Convergence from independent
directions is stronger evidence than any one line, and is the reason this is
its own entry.

**What does not change.** Fixed-threshold `r1` with a stated operating
envelope remains the **ratified architecture** and ships. This entry re-opens
nothing: the limits are stated, stratified, and Track-B-falsifiable
(VUV11/VUV13), which is the honest form for a bounded detector.

**The successor is identified, and its blocker is named.** The pitch-lag
correlation dissolves all three: aspiration outright (D3 measured +0.482
voiced vs **+0.013** aspiration at lag 89 — the voiceless-vowel envelope has
no peak at the pitch lag), the coloured floor generally (noise colour decays
by lag 89 — a ~20× lower floor than lag-1 on D3), and D2 at least
sign-correctly (+0.068 vs −0.020, still marginal — D2 stays hard for any
correlation feature). Its blocker is the **F0 circularity**: a pitch-lag
statistic needs an F0 estimate, and F0 estimation conventionally needs a
voicing decision — whether voicing gates F0, F0 gates voicing, or the two
co-estimate is a genuine open research question (docs/vuv_c1_decision.md
§Further research), with the lag-band generalization (VUV4's jitter knob) and
the conditioning-corner interaction (VUV12) attached to it.

- **Status:** finding recorded; the architecture stands. **Step 9's YIN work
  inherits this case already made** — the successor's motivation does not need
  re-deriving, only its circularity resolved. Cross-ref VUV11, VUV13,
  docs/vuv_rho_env.md, docs/vuv_c1_decision.md §Further research.

### VUV15. "C" and "E" identified: the two never-reconciled voicing implementations, and the evidence that rejected each

C and E are referred to throughout step 7's ledger and decision docs as the two
never-reconciled voicing implementations in the prior research code, and the
evidence rejecting each is the entire basis for the ratified decision-rule type
(fixed threshold over a trained model) — but neither was identified anywhere in
this repo, and the rejection evidence existed only in reasoning history. This
entry closes that gap **from source**. It records *why* the decision was taken,
not *whether*; the decision is ratified and is not re-opened here.

**Both share the feature layer and nothing else.** Each calls
the reference VUV feature extractor — the five Atal-Rabiner features we golden-mastered
(VUV7) — and then diverges completely.

#### C — the unsupervised per-utterance GMM voicing detector

End-to-end: mean-subtract and peak-normalize the signal → the reference VUV feature extractor
(32 ms / 10 ms / `nar`=16) → **`gaussmix(FM,[],[],3,'v')`: an unsupervised
3-component GMM fit to the input signal's *own* feature matrix** — there is no
training corpus at all, C refits per utterance → heuristic component
identification (lowest mean `Es` = silence; of the remaining two, lower mean
`Nz` = voiced, higher = unvoiced) → the GMM-likelihood step → per-frame argmax → labels
{1 = silence, 2 = unvoiced, 3 = voiced} → `medfilt1(vus,3)` on the **label
sequence** ("get rid of spurious frames" — see the correction note below) →
expansion of frame labels to per-sample labels. **C is live but uncaptured:**
the reference weighted-GIF driver and the reference multi-file driver call it; no golden capture covers it.

#### E — the supervised Mahalanobis minimum-distance voicing detector

End-to-end: the reference VUV feature extractor → Mahalanobis distance from each frame's feature
vector to three class centroids (`m` 3×5, `C` 5×15, one 5×5 covariance per
class) → minimum-distance assignment → labels {−1 = unvoiced, 0 = silence,
1 = voiced}. **E is the paper's own decision rule** (Atal & Rabiner Eq. (10),
minimum Mahalanobis distance with per-class covariance — VUV10), where C has
no paper basis. Its parameters come from the VUS parameter loader → the TIMIT training routine:
**supervised training on TIMIT** — reads SPHERE `.wav` via `readsph`, reads the
paired `.phn` phone labels, the phone-to-label mapper maps phones to {s, u, v} (vowels,
semivowels/glides, nasals, and the voiced fricatives `v`/`dh`; explicitly "No
Stops or Affricates", so voiced stops are labelled unvoiced), partitions frames
by label, and takes per-class mean and covariance. **E is orphaned:** nothing
in the prior research code calls the supervised detector.

#### Why they were never reconciled (DESIGN §9 step 7's premise, from source)

They disagree on **everything below the feature layer**, not on one axis:

| | C (the unsupervised GMM detector) | E (the supervised min-distance detector) |
|---|---|---|
| decision rule | unsupervised GMM + likelihood argmax | trained Mahalanobis min-distance (the paper's Eq. (10)) |
| training | **none** — refits the input signal per utterance | supervised, on TIMIT via `.phn` labels |
| class identification | heuristic on the fitted components (min `Es`, then min `Nz`) | fixed row order (s, u, v) in the trained `m` |
| label encoding | {1, 2, 3} = sil, unvoiced, voiced | {−1, 0, 1} = unvoiced, sil, voiced |
| post-processing | 3-frame median filter on the label contour | none |
| output | frame labels **and** per-sample labels | frame labels only |
| status | live (called by the reference weighted-GIF driver) but uncaptured | orphaned (no caller) |

**This is the fact that makes step 7 define-the-target at the decision layer:**
a decision oracle would have had to be C or E, and they are two mutually
inconsistent stages — differing in rule, training, class identification, label
encoding, and granularity — neither reconciled to the other, only one on any
live path, and that one uncaptured. There is no canonical decision behaviour to
reproduce. (The *features* remain capture-and-match precisely because both
implementations share the reference VUV feature extractor unchanged — VUV7's fork-scoping.)

#### The rejection evidence

**C — rejected on determinism.** `gaussmix` is unsupervised EM: component means
are randomly initialized and EM converges to an init-dependent local optimum, so
**the same input can yield different component means, and hence different
labels, on different runs**. That is disqualifying here for a structural reason,
not a stylistic one: this project's tests are deterministic same-input
comparisons (golden master at rtol 1e-10…1e-12; synthetic known-value). A stage
whose output varies run-to-run on identical input **cannot be golden-mastered
and cannot anchor a regression test at all**. C's identification heuristic is
independently fragile by its own record: three of the five corpus notes in
the centroid record file read "all voiced (no sil)", i.e. a 3-component GMM fit
to data containing one class, where "lowest mean `Es` = silence" necessarily
mislabels.

**E — rejected on licensing (decisive) and generalization (backstop).**

- **(b) Licensing, categorical.** E's only parameter source is the TIMIT training routine,
  which trains on **TIMIT** (LDC-distributed under licence). No trained
  parameter set is stored in the repo at all, so shipping E would mean
  re-deriving from TIMIT — re-entering the same chain. **A parameter set whose
  derivation chain runs through a non-redistributable corpus cannot ship
  Apache-2.0 regardless of its accuracy.** The argument is about the derivation
  chain, not the numbers' quality: it is categorical, not empirical, and no
  accuracy result could answer it. This settles the option actually on the
  table.
- **(a) Generalization, the backstop.** It closes the only residual (b) leaves
  open: a *hypothetical* cleanly-trained model. The project cannot build one
  anyway — **there is no redistributable corpus with frame-level V/U/S ground
  truth available to it**, which is why step 7 is define-the-target and why the
  fixtures are synthetic. **(b) settles the option on the table; (a) shuts the
  door (b) leaves open.** Ratified in that order.

#### The centroid record file — what it actually is (correction)

The reasoning history recorded this file as E's shipped trained centroids from
non-redistributable clinical corpora. **Re-read from source, that attribution is
wrong in its specifics**, though it does not disturb the decision:

- **Nothing reads it.** No code path in the prior research code opens it;
  the supervised detector takes `m`, `C` as arguments, and their only producer is
  the TIMIT training routine. It is a lab-notebook record, not a shipped parameter set.
- **It is structurally incapable of driving E:** it stores weights and 3×5 means
  only — **no covariances** — and the supervised detector requires all three 5×5 class
  covariances.
- **It cannot be the TIMIT training routine's output:** that function requires TIMIT `.phn`
  label files and SPHERE `.wav`, and none of the five corpora named is TIMIT.
  Its structure (a weight triple summing to 1, plus three 5-D means) matches
  `gaussmix`'s returns, so it is a record of **C's** per-corpus GMM fits.
- **Five sets, not two**, and the clinical corpora *are* named among them:
  `MGH` (Sil-Voi-Sil), `InriaData` (all voiced, no sil), `Talromur` (mixed),
  `vpd` (all voiced, no sil), `OpenGlot II` (all voiced).
- **Its rows are in arbitrary order.** They are `gaussmix` components, whose
  ordering is a fit artifact — which is exactly why the unsupervised GMM detector carries
  its "Logic to determine which mixture component is which" block.

**The divergence numbers, re-read rather than transcribed.** The ~7× (`Nz`) and
~24 dB (`Es`) figures carried in the reasoning history **reproduce exactly —
7.10× and 23.7 dB — but only under the reading "row 3 = voiced"** (the supervised
detector's convention). **That reading is refuted by the file's own content:** it makes
Talromur's voiced centroid `Nz` = 156.05 (≈2.4 kHz dominant — fricative, not
voiced) while the same corpus carries a row at `Nz` = 24.03 (≈375 Hz — voiced).
Under the unsupervised GMM detector's own identification logic — the logic that actually
consumes `gaussmix` output — the voiced centroids diverge by **2.58× on `Nz` and
8.9 dB on `Es`**, and Talromur's `Nz` = 156.05 falls out as unvoiced, which is
internally coherent. **The defensible figures are ~2.6× and ~8.9 dB.**

This softens the backstop's quantitative force and **changes nothing about the
decision**: (b) is decisive, categorical, and untouched. (a) survives — 2.6× in
zero-crossings and 8.9 dB in energy across five corpora is still material
divergence between voiced centroids, and the row-order ambiguity is itself
evidence that the artifact is a lab record rather than a usable trained model.

- **Status:** documentation gap closed from source; decision unchanged and not
  re-litigated. Cross-ref: **DESIGN §9 step 7** (the define-the-target framing
  and the decision-rule-type lean this evidence underpins); **VUV7** (the
  fork-scoping — features are capture-and-match, only the decision is
  define-the-target, because C and E are what a decision oracle would have had
  to be); **VUV11** (the guarded joint route — any return to a multivariate rule
  needs a redistributable corpus, which E's rejection establishes does not
  exist); **VUV10** (the paper's decision architecture, which E implements).

### VUV16. The sub-band check is not near a false-positive boundary for modal speech — the warn-not-raise ruling is more conservative than it needs to be

Measured on the H4 fixture (2026-07-17), against a prediction written before the
fixture existed. This is the finding the H-series' boundary probe was built to
produce, and it is recorded **either way** by prior agreement — a silent H4 is
not "nothing happened".

- **The concern it tests.** VUV12 ruled that the sub-band check **warns** rather
  than raises because its threshold is shakier than the DC check's: 50/60 Hz hum
  sits at the bottom of modal phonation, so a ~70 Hz band edge might
  false-positive on a genuinely low male voice. That concern is what bought the
  named cost — **hum only warns**.
- **The measurement.** H4 is a clean `synth_vowel` at **F0 = 85 Hz** (a
  realistic low-male floor). Predicted: sub-70 Hz energy fraction < 0.02, check
  silent. Measured: **0.0008** — silent, with **~125× margin** below the 0.1
  threshold, two orders from firing.
- **Why, structurally (this is the part that generalizes).** A periodic signal's
  **fundamental is its lowest component**: an 85 Hz voice has *no* harmonic
  below 85 Hz, so its sub-70 Hz content is spectral leakage only. **Hum at
  50/60 Hz sits below the fundamental of any modal voice, not among the
  harmonics of a low one.** The feared overlap between the check's band and
  modal phonation does not exist — the two are separated by construction of what
  phonation *is*, not by a lucky threshold choice.
- **The finding:** the warn-not-raise ruling is **more conservative than the
  evidence requires**. It is not wrong — it costs only that hum warns instead of
  raising — but the reason it was chosen (proximity to a false-positive
  boundary) is not borne out for modal speech. **Not re-opened here:** the
  ruling stands until Track B, where real recordings can show whether anything
  else (very low F0, vocal fry, non-modal phonation, sub-70 Hz room modes) sits
  near the edge in a way synthetic vowels do not. This entry exists so that
  decision is made on evidence rather than on the original concern's momentum.
- **The bound on the finding.** It says nothing about **F0 < 70 Hz**: below the
  modal floor a signal genuinely carries sub-phonation energy, so firing there is
  the edge working, not failing. The fixture deliberately contains no such case
  (it would test the constant's arithmetic, not the physical question).
- **Status:** finding recorded; ruling unchanged, revisitable at Track B with
  this as its input. Cross-ref VUV12 (the ruling and its named cost),
  `tests/synthetic/README.md` (the H-series predictions and outcomes).

### VUV17. The shipped detector's known limits, measured

VUV11's second forward requirement, due now that the classifier exists: the
limits become **documented properties of a shipped artifact**, not analysis.
Consolidated here so a user reads one place; VUV11, VUV13 and
[docs/vuv_rho_env.md](docs/vuv_rho_env.md) carry the reasoning and are not
restated. Measured with `detect_voicing` on the committed fixtures
(2026-07-17), stratified per region — never aggregate (VUV5/VUV11), because an
aggregate score would hide precisely these.

- **Voiced frication reads non-voiced** (VUV11's C′). D2's voiced fricative
  measures `r1` = −0.055, below every threshold the declared `rho_env` range
  admits: **measured 0.00 voiced**, against `voiced_modal` 1.00 and
  `unvoiced_fricative` 0.00. A fixed threshold on a lag-1 statistic
  systematically labels voiced frication non-voiced. Falsifier unchanged
  (Track B, real voiced fricatives at VFR ≤ 0 dB against EGG).
- **Strong aspiration is not covered at any α** (VUV13). D3's *mild* instance
  (band-limited, `r1` = 0.271) is correctly rejected at every admissible
  `rho_env` (measured 0.00 at 0.53/0.67/0.81) — but that is the fixture being
  mild, not the limit being absent: aspiration is acoustically a voiceless
  vowel, so its ρ approaches the co-articulated vowel's and no threshold
  excludes it.
- **No admissible `rho_env` detects breathy voice at HNR ≈ 0 completely.**
  This is the user-facing limit, and it is *stronger* than the "straddle" the
  earlier record described — stated first because it is what a caller needs.
  Measured at the classifier assembly: breathy's `r1` is a per-frame
  distribution spanning **[0.593, 0.661]** (mean 0.625), so even at the range's
  **floor** (ρ_env = 0.53, threshold 0.6027) the threshold cuts its lower tail
  — **0.83 of the region reads voiced there, never all of it** — and at the
  **midpoint** (0.67) **none** does. Full detection of the region would need
  ρ_env ≤ **0.520**, *outside the declared [0.53, 0.81] range entirely*.
  - *Character of the limit:* with `rho_env` required and defaulted nowhere,
    how much of breathy is recovered is **a property of the caller's
    configuration**, not a fixed limit of the detector — the required
    parameter earning its cost — but the ceiling above (never complete, at any
    admissible envelope) holds regardless of the caller.
  - *Provenance correction:* the earlier straddle read breathy against its
    region **mean** (0.625) and concluded it survives for `rho_env` < ~0.537.
    That was too loose — the per-frame span is what governs. Same shape as
    ρ_env caveat (a)'s missed prediction: reasoning from an aggregate where the
    per-frame distribution was what mattered. Corrected in place in
    [docs/vuv_rho_env.md](docs/vuv_rho_env.md).
  - *Does not move the range:* declared-not-derived, Track-B-adjudicated; a
    measurement that makes a limit worse is no more a licence to move a
    parameter than one that makes it better.
- **Hum warns, then misclassifies** (VUV12's named cost, now observed). H2 —
  hum with no phonation, ground-truth N — warns and is then labelled **voiced
  throughout**. Hum is genuinely periodic, so no threshold at any α rejects it;
  only conditioning does, and `condition()` returns it to 0.00 voiced. DC by
  contrast **raises** (H1) and the detector refuses.
- **D1's decay tail is lost by design** (VUV5). `voiced_decay` runs SNR
  30 → −2 dB labelled V throughout: measured 0.92 voiced at the midpoint,
  0.75 at 0.81. A detector *must* lose the low-SNR end — asymptotic-in-the-tail,
  provable only under SNR-stratified scoring, not a defect.
- **Status:** documented properties of the shipped detector. Binds the scorer
  (VFR/HNR/SNR-stratified reporting) and any user-facing docs. Cross-ref VUV5,
  VUV11, VUV12, VUV13, docs/vuv_rho_env.md.

### VUV18. The "mask exercise" was cited as proving the frame-lookup rule; it never touched project() (rule 2, third instance)

Found while building the derived per-cycle mask (2026-07-18), by reading the
committed test. `test_d1_derived_mask_nans_nonvoiced_cycle_keeps_voiced_finite`
was cited across five gates as proving the mask's GCI->frame lookup. **It never
called `project()`.** It builds the mask from `_label_at` -- ground-truth region
membership by GCI sample -- and asserts against a GCI **beyond the guard band
W**, which is exactly the regime where `project()` (nearest-centre) and region
membership *agree*. So the test structurally could not distinguish the
production lookup from any other membership rule: **a test that could not fail
for the reason it was cited.** The two things production actually does -- map
each GCI through `project()`, read a real `VoicingTrack` verdict -- were neither
exercised nor asserted.

- **What it did prove** (and still does): the `apply_cycle_mask` nan-assignment
  mechanics, and region membership beyond W. Its own docstring was honest about
  using ground-truth labels; the false claim lived in how it was *cited*, not in
  the test.
- **Closed:** `test_d1_voicing_mask_real_path` runs the production path --
  `detect_voicing` -> real track -> `apply_voicing_mask` with the `project()`
  lookup (`VoicingTrack.frame_index`) -- and the committed seam-mechanics test
  now carries a note pointing at it so the mis-citation cannot recur.
- **Honest limit of even the fixed test:** within-W boundary behaviour is a
  don't-care by construction (the guard band), so `project()`'s
  rounding-at-the-boundary is *exercised* but not *asserted* against ground
  truth -- there is nothing to assert, the region label is ambiguous there. That
  rounding is pinned independently in `test_vuv_grid`
  (`test_projection_nearest_center_known_samples`: 255->0, 416->1, 736->3), so
  the coverage exists -- just not in D1, and confirmed to exist rather than
  assumed.
- **This is rule 2 (evidenced vs cited) firing a third time** -- next to the
  false `medfilt1` corroboration (VUV15) and VUV16's non-existent overlap -- and
  the **first instance touching a test's claimed coverage** rather than a doc's
  claim. All three were caught the same way: by reading or measuring, never by
  re-reasoning. Recorded in docs/working_method.md rule 2 as a standing case.
- **Status:** gap closed; the working-method rule it instances is the durable
  takeaway. Cross-ref docs/working_method.md (rule 2), VUV15, VUV16.

---

## Step 8 (weighted-LP GIF) — forward findings

Watch-items and established conventions surfaced while gating the step-8 milestone
(closed-phase, AME, symmetric/asymmetric Gaussian weighted LP). Like the Step 7
section, these are design findings for an in-progress milestone, not port-vs-reference
reproduction facts — except where noted as a pinned convention with a golden master.

### GIF1. GIF weighting convention (W vs W^2): reproducing v_lpccovar requires `weights = W^2`

Established 2026-07-18 by golden master against the reference, at the step-8 gate,
before any weighting function was written. **This is the single seam every step-8
method routes through**, so it is pinned first.

- **The two conventions.** The reference VOICEBOX `v_lpccovar` applies its weight
  vector as `dm = dm.*w(cs)` and `sc = s(cs).*w(cs)` (v_lpccovar.m:113–114, 128–129),
  so it minimises `sum W^2 * resid^2` — its own header states "the error at each
  sample is weighted by W^2". `voicekit.lpc.lpc_covar` does `sw = sqrt(w); sw*design`
  (covariance.py), minimising `sum w * resid^2` — the error weighted by `weights`
  *linearly*. Therefore a caller reproducing a `v_lpccovar` run with reference weight
  vector `W` must pass **`weights = W**2`**, not `W`. Every step-8 method
  (the reference weighting constructor → the reference weighted-LP solve wrapper →
  `lpccovar(sp, nar, T, w)`) produces such a
  `W` and feeds it to the reference this way, so all of them inherit this convention.
- **Why it had never been checked (the mechanism, not just the conclusion).** The
  pre-step-8 weighted-covariance tests used only uniform weights
  (`test_uniform_weights_match_default`), a zero-mask
  (`test_zero_weight_ignores_corrupted_region`), and scaling
  (`test_scaling_weights_leaves_coefficients_unchanged`). None can disambiguate, and
  the reason is structural, not a matter of degree:
  - **Under uniform weights `W = c·1`, the two conventions differ only by a global
    scale** — `W` is the constant vector `c·1`, `W^2` is the constant vector `c²·1`,
    and the two are proportional. The covariance solve is scale-invariant (see
    `test_scaling_weights_leaves_coefficients_unchanged`), so it returns the identical
    AR under `c·1` and `c²·1`. The uniform case is therefore a *special case of the
    scaling blindness*, not independent coverage.
  - **The scaling test is scale-invariance testing itself** — `a(w)` vs `a(3.7·w)` —
    so it cannot possibly separate `W` from `W^2` (which are related by a non-constant
    factor `W` only when `W` is non-uniform). It is **zero evidence** for the
    convention, not weak evidence: a passing scale-invariance test structurally
    *guarantees* blindness to whether the argument is `W` or `W^2`.
  - The zero-mask has weights in `{0,1}`, where `W = W^2` exactly, so it is invariant
    by identity.
  This is the rule-2 shape (docs/working_method.md): a passing test read as coverage
  when it is structurally incapable of exercising the thing claimed. Getting the
  convention wrong does not crash or NaN; it silently solves a different least-squares
  problem and returns a plausible glottal flow — the silent-numerical-drift failure
  this project exists to prevent.
- **A second way to blind the probe.** W and W^2 also coincide when the signal is
  **exactly fittable** at the analysis order: `resid ≡ 0` makes the objective
  weight-independent, so both conventions return the identical exact AR and the probe
  reports a false "agree". The in-tree example is
  `test_exact_recovery_from_impulse_response` (an order-4 impulse response recovered
  with error ≈ 1e-18). The probe fixture is therefore chosen to be *not* low-order
  predictable, and three pre-capture checks (nonzero residual; W vs W^2 normal-equation
  entries differ; `lpc_covar(W).a` ≠ `lpc_covar(W^2).a`) enforce non-degeneracy before
  the reference is run.
- **The capture (arbiter).** `tests/golden/capture/capture_wcovar.py` builds a
  hand-checkable order-2 fixture — `s = [1,-2,3,1,-4,2,5]`, monotone distinct weight
  `W = [1,2,3,5,7,11,13]` — runs `v_lpccovar` (weight applied as the reference does)
  on both the plain 2-output path and the 3-output `dc_offset` path, and writes
  `tests/golden/wcovar_weight_convention.npz`. Result: `weights = W^2` reproduces the
  reference AR to **6.66e-16 (machine-eps)** on both paths; `weights = W` is off by
  0.069 (plain) / 0.040 (dc_offset). **Confirmed branch-independent**: both the plain
  and `dc_offset` branches of `v_lpccovar` apply the weight identically (`dm.*w`), so
  the `W^2` convention holds in both — the `dc_offset` path is the one the reference
  weighted-LP solve wrapper actually calls (`[ar,ee,dc]=lpccovar(...)`, the same three-output form VUV's
  `alp1`/`Ep` used). (The AR *values* differ between the plain and dc paths — the dc
  path fits a DC term jointly — which is the model changing, not the convention.)
- **Pinned by:** `tests/test_lpc.py::TestWeightedCovarianceConvention` (machine-eps,
  both paths, plus the reverse assertion that `weights = W` is measurably wrong).
  Convention noted at the `sqrt(w)` site and in the docstring of `covariance.py`.
- **Status:** established convention, pinned by golden master — not a divergence
  (the port matches the reference when passed `W^2`). Step-8 method implementations
  must square the reference weighting constructor's weight vector before calling `lpc_covar`.

### GIF2. Closed-phase design fork: locked to the reference (full-frame solve + 0/1 weight mask); the interval-restricted alternative is deferred and item-9-gated

Decided 2026-07-18 at the step-8 gate, framed the same way the `r1` decision was
(docs/vuv_r1_null.md, VUV14): a parity target is chosen **now**, and the alternative is
recorded as a named, deferred option reopenable only against evidence that does not yet
exist — not carried open into implementation.

- **What the reference does.** The reference closed-phase method does **not** restrict
  the LPC solve to the closed phase. The reference weighted-LP solve wrapper solves over the full analysis
  frame (`nar = ceil(fs/1000) = 20` at `fs = 20000`, frame length ~640 samples from the
  32 ms / 16 ms grid), and the closed phase enters only as a **0/1 weight** that zeros
  the open phase and a `cpDelay`-long return phase after each GCI. Verbatim, the mask
  construction (the reference weighting constructor, `case 'cp'`):
  ```matlab
  w=ones(1,nsp);
  ...
  cpDelay=round(cpDelay*fs);
  ...
  for in=1:length(gci)-1
      if (gci(in+1)-gci(in))>maxSamplesPerCycle
          % ... interval between voiced spurts, leave w=1 except suppress
          w(max(1,(gci(in)-cpDelay)):gci(in))=0;
          continue;
      end;
      % Suppress return phase
      w(gci(in):(gci(in)+cpDelay))=0;
      % Suppress open phase
      w(goi(in):gci(in+1))=0;
  end;
  ```
  So the weight is `1` on the closed phase and `0` on `[gci, gci+cpDelay]` (return) and
  `[goi, gci_next]` (open). The solve interval is the **frame**, always `>> order`, so
  **C8's short-frame order reduction (`pp = min(p, nc-d0)`) is never reached on this
  path** — `nc` is the frame length.
- **Locked target.** The full-frame solve + 0/1 closed-phase weight mask is the parity
  target for the step-8 closed-phase method. Combined with GIF1: the mask `w ∈ {0,1}` is
  passed to `lpc_covar` as `weights = w**2` — which for a 0/1 mask equals `w` (idempotent),
  so the convention is a no-op here, but the method layer must still square uniformly for
  consistency with the non-binary Gaussian/AME weights.
- **Deferred alternative (named, item-9-gated).** VOICEBOX `v_lpccovar` note (4) supports
  an interval-restricted closed-phase analysis: set `T`-matrix rows to the short
  closed-phase intervals themselves (multiple disjoint segments per row if a closed phase
  is < 2 ms), solving **only** over the closed phase. That design (a) reaches C8's
  order-reduction path (short-by-construction intervals) and (b) has different rank
  behaviour (see GIF3). Choosing between full-frame-weight and interval-restricted has an
  **accuracy dimension that is unmeasurable until item-9's scoring harness exists**
  (§5 Track A/B, OpenGlot/APLAWD). Leaving it open would not preserve an *informed*
  decision — nothing in step 8 can make that call — it would defer an *uninformed* one to
  a worse moment and let it resolve against whatever fixture is on screen at resolution
  time (rule 1). So it is decided-for-parity now, reopenable only against item-9 evidence.
- **Discipline binding.** The parity obligation binds the method layer to the reference;
  any departure is a **define-the-target decision needing its own out-of-sample
  justification** — the same rule as `r1` (VUV14), new milestone. Cross-ref
  docs/vuv_r1_null.md, DESIGN §5 (Track A/B), and C8.
- **Status:** locked to reference for parity; interval-restricted alternative deferred,
  item-9-gated.

### GIF3. Effective-support < order: a rank-deficiency degeneracy distinct from C8 — reference (basic solution) and voicekit (min-norm) diverge silently

Found 2026-07-18 by construction (define-the-target: no committed fixture is guaranteed
to drive a closed-phase frame below effective-support order, so a synthetic
known-degeneracy fixture is the oracle). **This is a different degeneracy from C8 and is
not folded into it.**

- **C8 vs GIF3.**
  - *C8* is **`nc < p`** (frame shorter than order): `v_lpccovar` reduces order
    (`pp = min(p, nc-d0)`), `lpc_covar` raises.
  - *GIF3* is **`nc >> p` but nonzero-weight support `< p`**: with a 0/1 closed-phase
    weight, a long frame's effective support (nonzero-weight sample count ≈ a few closed
    phases) can fall below the order while the frame length far exceeds it. The weighted
    normal equations go **rank-deficient on a long frame**. `pp = min(p, nc-d0)` does
    **not** trigger (it keys on `nc`, the frame length, not on effective support), so
    `v_lpccovar` does **not** reduce order here — it solves the rank-deficient system as-is.
- **The GIF1 convention does not settle this.** The `W^2` pin used a full-support,
  full-rank system; it says nothing about *which* solution each side returns under
  rank-deficiency. That is a separate question, and this entry has its **own** fixture
  (the convention fixture structurally cannot reach the degeneracy).
- **The fixture (synthetic, hand-verifiable degeneracy).** `order = 4`, `N = 40`,
  `s[n] = sin(0.7n) + 0.3·sin(1.9n)` (deterministic, chosen by construction not fitted),
  0/1 weight nonzero only at predicted-sample indices `{10, 20, 30}`. The three explicit
  checks (analogue of GIF1's pre-capture gate — proving the fixture *reaches* the
  degeneracy, not merely looks like it):
  - (a) `nc = 36 > order = 4` (frame is long);
  - (b) nonzero-weight support `= 3 < order = 4` (support is short);
  - (c) `rank(sqrt(w)·design) = 3 < 4` (weighted design is rank-deficient).
- **What each side returns (found, from code and the reference, not assumed).** Both are
  **finite — no crash, no NaN** — and they **differ**:
  - `voicekit lpc_covar(weights=w).a = [1, -0.322907, -0.230831, 0.097037, 0.721682]`
    — the **minimum-norm** solution (numpy `lstsq`/SVD; confirmed it matches an explicit
    min-norm solve), `‖coef‖₂ = 0.829`.
  - `v_lpccovar(...,w) AR = [1, -0.378368, -0.107892, -0.0, 0.749237]` — MATLAB `\`
    (`aa = dm\sc`) returns a **basic solution** (rank-revealing QR: at most `rank(A)`
    nonzero components — note the `-0.0` third coefficient), `‖coef‖₂ = 0.846`. MATLAB
    emitted a rank-deficiency warning at the backslash sites (`v_lpccovar.m` lines 116,
    131), confirming it reaches and solves the deficient system rather than reducing or
    erroring.
  - `max|Δ| = 0.123`. **The two return different finite AR silently** — the min-norm
    (numpy) and basic (MATLAB `\`) solutions of the same rank-deficient system.
- **Not fixed this round (deliberate).** No side is changed. This entry establishes the
  behaviour and flags it for the **closed-phase implementation gate**, where the policy —
  guard-and-raise, skip-cycle, or reproduce-reference-basic-solution — gets decided.
  Per rule 1 that policy must be settled **before** any fixture shows which choice keeps
  the most cycles green. Characterized (not asserted-for-parity) by
  `tests/test_lpc.py::TestWeightedRankDeficiency`.
- **Status:** decided at the closed-phase gate (second round) — skip-frame/mask; see
  GIF5. The characterization above stands unchanged.
  Cross-ref C8, GIF2 (the interval-restricted alternative reaches this too).

### GIF4. Two-revision Gaussian weighting: the current reference weighting constructor is authoritative; its superseded predecessor is the earlier revision (DESIGN §5's missing `-0.5`, located)

Established 2026-07-18 from source (the parameter pins in the reference parameter file), before any
Python weighting function exists to fit to — rule 1 clean. The authority is determined
by which file the reference parameter file's parameters fit, **not** by matching Python output to a
revision.

- **The `rgauss` difference is DESIGN §5's named example, now located.** Verbatim:
  - superseded (the earlier weighting constructor, `case 'rgauss'`): `sig2=sig^2;` then
    `gg = gg + kappa*exp(-(nn-gci(ii)).^2/sig2);` — i.e. `exp(-x²/σ²)`, **missing the
    `-0.5`** (not a proper Gaussian).
  - current (the reference weighting constructor, `case 'rgauss'`): `sig2=sig^2;` then
    `gg = gg + kappa*exp(-0.5*(nn-gci(ii)).^2/sig2);` — i.e. `exp(-0.5·x²/σ²)`, a proper
    Gaussian.
  This is exactly the "missing `-0.5` factor in a Gaussian weighting exponent, introduced
  silently between two revisions of the same function" that DESIGN §5 cites as the
  project's motivating golden-master example — now identified in the tree.
- **`agauss` and `cp` also differ** (corroborating that these are two genuine revisions):
  - `agauss`: current caps `N0` at `maxSamplesPerCycle` (`N0=min(gci(ii)-gci_last,maxSamplesPerCycle)`)
    and clamps `w = max(0, 1-gg)`; the old version does neither (`N0=gci(ii)-gci_last`
    uncapped, `w = 1-gg` can go negative). Current also seeds `gci_last=max(1,gci(1)-maxSamplesPerCycle)`
    vs old `gci_last=max(1,gci(2)-gci(1))`.
  - `cp`: current is the `cpDelay` loop (GIF2 quote); old is a `cumsum`/`cpFrac`
    construction (`w(adgci)=1; w(goi)=-1; w=cumsum(w)` with a `cpFrac`-based non-voiced
    fill).
- **Authority evidence (from source, pre-Python).** The reference parameter file pins parameters that
  fit **only** the current file:
  - `case 'cp'`: sets `cpDelay` but **not** `cpFrac` — and comments the latter out
    (`%par.wpar.cpFrac = 0.8;`). The old `cp` *requires* `cpFrac`; the current `cp`
    comments it out (`%cpFrac = par.cpFrac;`). So the reference parameter file fits the current `cp`.
  - `case 'agauss'`: `kappa = 0.99; alpha = 0.1; r = 2;` with the comment "parameters
    recommended in *Zalazar et al, Symmetric and asymmetric Gaussian weighted linear
    prediction for voice inverse filtering, 2024*". These are the current `agauss`'s
    parameters.
  The target is thus chosen from the parameter pins (source), before any Python exists —
  no fit to Python output.
- **Method → paper mapping, and the single-oracle flag.** `rgauss` = **symmetric** and
  `agauss` = **asymmetric** Gaussian weighting (Zalazar et al. 2024); `ame` cites Alku
  ("Improved formant frequency ..."). **No paper PDFs are in the tree, and no independent
  MATLAB cross-check exists** — COVAREP carries only IAIF variants, not CP/AME/weighted-LP
  GIF. So the prior research code is the **sole behavioural oracle** for all three methods:
  these are golden-master-against-the-reference with **no second independent oracle**. That
  **raises the value of the synthetic-known-value hand-checks** when these methods are
  implemented — with only one behavioural oracle, the "computes what I expect" check
  (assert the decomposition, not just the final value) carries more weight than usual.
- **Amendment (2026-07-23) — the authority has a direct invocation pin, stronger than
  param-fit.** The establishment above is *config-compatibility inference* (which
  revision the reference parameter file's pins fit) — corroboration-shaped under rule 2.
  A direct pin exists and is stronger: the reference weighted-LP solve wrapper calls the
  weighting constructor **by name**, and the only file defining that symbol is the
  authoritative (`-0.5`-present) one; the superseded predecessor defines a
  **differently-named** symbol that nothing in the tree calls (grep: zero callers, dead).
  So MATLAB path resolution provably invokes the `-0.5`-present file in the live pipeline
  — authority-by-invocation, not merely authority-by-param-fit. The param-fit remains
  valid corroboration; the invocation is the establishment. (Surfaced at the GIF10
  capture gate; the earlier round deferred amending here until the implementation gate.)
- **Status:** authority established (current authoritative, old superseded); `-0.5`
  example located. Ledgered ahead of the Gaussian method implementation; the capture
  target is the current reference weighting constructor.

### GIF5. Rank-degeneracy policy decided: skip-frame — a deficient frame's cycles are masked NaN. A named departure where the reference has no defined value

Decided 2026-07-19 at the closed-phase gate (second round), from source and charter.
Rule-1 discipline: no candidate policy was run against any fixture; the only fixture
numbers consulted are the degeneracy-*frequency* measurements (GIF3 and the gate's
mask-support counts), which are policy-independent — the same frames are deficient
under every candidate policy — and no surviving-cycle count was computed for any
policy.

- **The policy.** When a closed-phase frame's weighted normal equations are
  rank-deficient (nonzero-weight support `< nar+1` on the `dc_offset` path is the
  documented sufficient condition; detection must be explicit, e.g. the solver's
  reported rank), the frame's AR is not used. The cycles that frame inverse-filters
  are masked ``NaN`` through the existing ``(mask, subset, value)`` convention
  (`apply_cycle_mask` / `apply_voicing_mask`, ``value = nan``), with the mask
  observable (a reason, not just a silent NaN), matching `apply_voicing_mask`'s
  precedent. Detection is per **frame** (the solve unit); propagation is to the
  cycles that frame filters — the degeneracy is not a per-cycle property.
- **Reproduce-the-reference is disqualified: there is no defined value to reproduce.**
  `v_lpccovar`'s degenerate path is bare — `pp=min(p,nc-d0)` keys on the frame
  length, never on effective support, and the weighted solve is
  `aa = (dm\sc).'` (v_lpccovar.m:116 dc path, :131 plain). The file contains no rank
  handling, no `pinv`, no warning of its own (grep: zero hits for
  rank/warning/pinv/cond); the rank-deficiency warning GIF3 observed is MATLAB
  `mldivide`'s own console warning. On a rank-deficient system `\` returns a *basic
  solution*, and **which** basic solution is an artifact of the pivoted-QR
  implementation (pivot order, LAPACK build) — neither the reference source nor
  MATLAB specifies it, so it is not stable-by-contract even across MATLAB releases.
  "Parity" here would mean writing a pivoted-QR solve specifically to reproduce an
  unspecified solver artifact — reintroducing the silent-numerical-drift failure
  DESIGN §5 names as the project's motivating example. There is a reference
  *solver's incidental output*, not a reference *value*.
- **Guard-and-raise is rejected.** One deficient frame would kill a recording
  end-to-end, and the gate measurement shows the case is live at ordinary F0
  (1/33 frames on `vowel_glide_16k`, support 12 < 17, driven by early GOI
  candidates 18–19 samples after the GCI against ``cpDelay+1 = 15`` zeroed) — so it
  is common on realistic high-pitch input, not a cold edge. An API that raises on
  any recording containing one short closed phase is unusable without every caller
  wrapping it. (C8's raise is a different situation: frame-shorter-than-order is a
  caller-configuration error, not a data-dependent property of healthy input.)
- **NaN-mask is the codebase's existing representation for exactly this.** A
  rank-deficient frame is genuinely uncomputable — the closed phase does not carry
  the information to determine the AR — and the NaN-for-uncomputable line is already
  drawn in `apply_voicing_mask`'s docstring
  (`src/voicekit/features/extract.py:90-95`): "``NaN``, not ``0.0``: a non-voiced
  cycle is *uncomputable* (no glottal source), which has no reference value — unlike
  the O1==0 degenerate branch, whose ``0.0`` is the reference's own defined output."
  Rank deficiency falls on the NaN side of that line for the same reason: no
  reference value exists.
- **Define-the-target, not reproduce-and-quarantine.** This is not a divergence from
  defined reference behaviour, because there is no defined value to diverge from;
  choosing skip-frame designs a new stage rather than correcting a reproduced quirk.
  Where the reference **is** well-defined the parity discipline binds unchanged
  (GIF2's full-frame + 0/1 mask lock); where it is not, the departure is deliberate
  with its reasoning ledgered here — the same decision shape as `r1` (VUV14) and
  GIF2's deferred alternative. Not filed under "Divergences from the reference":
  that section catalogues departures from *defined* reference behaviour justified by
  accuracy results; this is a policy for a case the reference leaves unspecified. If
  item-9 corpus evidence ever favours another treatment (e.g. order reduction on
  effective support), that is a reopen-with-evidence, like GIF2's alternative.
- **Status:** decided — skip-frame/NaN-mask. GIF3's characterization stands;
  implementation lands with the closed-phase method (after GIF6's exposure commit).

### GIF6. `GciResult` gains `goi_candidates`: the reference GOI-selection step's input exposed, not recomputed (API shape pinned; not yet implemented)

Decided 2026-07-19 at the closed-phase gate (second round), from the gate's Q2
finding. The reference closed-phase mask does **not** consume the detector's
DP/postGOI ``goi`` sequence (the one `GciResult.goi` reproduces): the reference
weighted-GIF driver discards that output and rebuilds a gap-free GOI sequence with
a separate **GOI-selection step** — a candidate-selection method due to the
maintainer (unpublished; being written up as part of voicekit — priority note,
2026-07-19). Its mechanism: for each cycle, compute an a-priori opening point
``coc = gci + ceil(APOP·dgci)`` (``APOP = voicebox('dy_cpfrac') = 0.3``, the
presumed closed-phase fraction; ``dgci`` the cycle length, the last cycle extended
zero-order); among the GOI **candidates** strictly inside the cycle, pick the one
minimising the squared distance to ``coc``; when the cycle has no candidate, fall
back to ``coc`` itself — so the output is total (never NaN). Its input is the GOI
candidate set, not the DP-selected openings, and the two GOI sequences are
materially different: they differ on 55/55 cycles (median |Δ| = 28 samples) on
`vowel_f0100_16k`, 9/62 on `vowel_glide_16k`, 0/66 (coincidentally) on
`vowel_f0120_8k`. So a NaN-fill of `GciResult.goi` cannot reproduce the reference
mask. The reconciliation is an API exposure, not a fill.

- **Expose, don't recompute.** The set the GOI-selection step needs is the
  detector's leftover set — candidate positions minus the DP-selected
  (pre-refinement) GCIs, a setdiff the reference detector computes **before** GCI
  refinement — which `detector.py:170–172` already computes
  (``leftover = ~np.isin(positions_1based, gci_dp)``) and currently discards after
  the GOI DP uses it. The field returns that computation. A second copy of the
  setdiff in `gif/` would be the two-copies-of-a-convention hazard this project
  exists to prevent; consuming what `yaga()` returns — never re-running detection —
  is the returned-not-accepted discipline `YagaResult.residual` established.
  Confirmed single-source: the candidate-vs-`gci_dp` setdiff exists at exactly one
  site (`detector.py:170`), and `GciResult` has exactly one construction site
  (`detector.py:270`).
- **Field shape.** ``goi_candidates: npt.NDArray[np.int64]`` — 0-based, sorted
  positions of the assembled candidates not selected as GCIs by the DP (the
  positions column of the reference's candidate matrix, − 1). **Positions only.**
  The reference carries a second column alongside the positions (the zero-crossing
  flag), but the GOI-selection step provably never consumes it: its in-cycle window
  (candidates strictly between ``gci`` and ``gci + dgci``) linear-indexes the whole
  N×2 matrix, and a flag value ∈ {0,1} can never exceed a 1-based ``gci ≥ 1``
  (fixture corroboration: flag column ∈ {0,1} on all three captures, min gci 274).
  Carrying it would be decorative.
- **`gci_dp` is NOT exposed.** The GOI-selection step takes the refined public
  GCIs (the driver passes the detector's post-refinement output — the sequence
  `GciResult.gci` already is) plus the candidate set. `gci_dp`'s only role is the
  setdiff, which stays internal to the detector.
- **`GciResult.goi` is unchanged** — NaN-for-absent stays the honest per-cycle
  opening estimate. The docstring must state why both fields exist so neither reads
  as redundant: ``goi`` = the detector's per-cycle opening estimate (what feature
  timing consumes); ``goi_candidates`` = the raw candidate set from which the
  closed-phase weighter reconstructs the reference's gap-free GOI sequence (the
  GOI-selection step above: nearest candidate to ``coc``, a-priori ``coc`` fill
  when a cycle has none). They are different objects on 55/55 cycles of the 16 kHz
  fixture.
- **setdiff-semantics nuance.** MATLAB `setdiff` dedups and sorts; `np.isin` keeps
  duplicates. No duplicate candidate positions occur on any fixture (241/237/207
  candidates, all unique; the isin-kept set equals the captured ``ret_goic[:,0]``
  exactly, content and order, on all three), but the guard test must assert the
  field equals ``ret_goic[:,0] − 1`` per fixture — which pins setdiff semantics if a
  duplicate position (a zero-crossing and a projected candidate on the same sample)
  ever arises; dedup at the field construction if so.
- **Commit sequencing (hygiene).** This is an additive change to an
  already-committed frozen result type. It lands as its **own commit, green in
  isolation, before any `gif/` code** — not bundled into the first closed-phase
  commit. Guard-test-first: the commit carries (a) a test proving existing YAGA
  output (``gci``, ``goi``, ``residual``) is bit-identical before/after the field is
  added, and (b) the golden assertion ``goi_candidates == ret_goic[:,0] − 1`` on all
  three fixtures. Besides the dataclass, the only production line that changes is
  the single construction site.
- **Status:** landed (2026-07-20). `goi_candidates` exposed on `GciResult`
  (0-based sorted int64, positions only), threaded out of the single existing
  setdiff, `goi`/`gci`/`residual` unperturbed (existing golden guard stays green),
  semantics pinned against `ret_goic[:,0]-1` (content+order on 16k; unit-level on
  all three). Ready for the closed-phase weighter to consume.

### GIF7. Step-8 capture shape: native-fs method capture; the reference's fs=20000 resample front-end is a documented non-target

Decided 2026-07-19 at the closed-phase gate (second round).

- **The fork.** The reference weighted-GIF driver hardcodes ``fs = 20000`` and
  resamples every input (``sp = resample(sp,fs,fs_sp)``) before detection *and*
  weighting, so every reference constant is a 20 k instantiation and reference
  GCIs/GOIs live on the 20 k grid. An end-to-end capture through the driver would
  golden-master the whole pipeline but requires (a) reproducing MATLAB's polyphase
  `resample` — a sizeable convention of its own — and (b) YAGA validity at 20 k,
  which is not established (YAGA is golden-mastered at 8 k/16 k); a native-fs run
  structurally cannot match such a capture. The method layer, by contrast, is
  fs-parametric from source: the weighted-LP solve wrapper —
  ``(sp, gci, goi, fs, par)`` — overrides ``wpar.fs = fs`` with its own fs argument
  (the reference parameter file's ``wpar.fs = 20000`` is dead on this path), and
  every constant is a formula in fs (``nar = ceil(fs/1000)``,
  ``cpDelay = round(0.9e-3·fs)``, ``maxSamplesPerCycle = ceil(fs/minF0)``,
  ``wl/inc = round(fs·{0.032, 0.016})``).
- **Ratified: native-fs method capture.** Drive the weighted-LP solve wrapper and
  weighting constructor (and the GOI-selection step, GIF6) directly at the fixture
  fs with the fixture GCI + candidate sets —
  the same shape as YAGA's own validation (native fs, instrumented capture). What
  step 8 ports is the weighted-LP method; the 20 k resample is the reference's I/O
  framing, not the algorithm.
- **GIF6 consistency.** The mask consumes the GOI-selection step's output (built
  from the refined GCIs plus the candidate set), so the capture needs the candidate
  set at the capture fs. The captured ``ret_goic`` is already native-fs (the YAGA
  captures ran the reference detector at 8 k/16 k), and `goi_candidates` is
  produced at whatever fs `yaga()` ran — the exposure supplies candidates at the
  method-capture fs by construction. Consistent.
- **What this shape does NOT validate (F1-style, deliberate).**
  - MATLAB ``resample(sp, 20000, fs_sp)`` — never reproduced, never asserted.
  - The 20 kHz operating point itself: ``nar = 20``, ``cpDelay = 18``
    (``round(18.0)``, exact), ``maxSamplesPerCycle = 400``, ``wl = 640`` are never
    exercised — the *formulas* are validated only at their 8 k/16 k instantiations
    (``nar = 8/16``, ``cpDelay = 7/14`` — where the round-not-ceil convention is
    live: 7.2→7, 14.4→14).
  - The driver's pipeline composition (resample → GCI/GOI detection → GOI
    selection → VUS gate → weighted-LP solve → save layout).
- **Item-9 interaction (documented, not resolved).** Reference outputs on corpus
  audio are produced at the 20 k operating point. When item-9's scoring harness
  compares methods, a native-fs voicekit run differs from the reference by
  *operating point*, not only by port fidelity. Item 9 must then either (i) give
  voicekit a 20 k-resample front-end for comparison runs — a define-the-target
  decision to take then, with its own resample-fidelity question — or (ii) score
  each system at its own operating point and document the difference. Until then
  the resample and the 20 k operating point are the step-8 analogue of F1's
  fixture limitation: a named, deliberate capture gap, not an oversight.
- **Status:** capture shape decided — native-fs method capture; the non-targets
  above are the ledgered gap.

### GIF8. Closed-phase weighter landed: validated native-fs against the reference; GIF5 Option B; two source findings

Landed 2026-07-21. `voicekit.gif.closed_phase_gif` implements the closed-phase
method against the pins: the GIF2 full-frame solve under the 0/1 mask, GIF1's
`W^2` weight (a no-op for the 0/1 mask, squared uniformly for the continuous-weight
methods to come), GIF6's GOI reconstruction, GIF7's native fs. Validated end-to-end
against the reference (the reference weighting constructor + `v_lpccovar` + `lpcifilt`,
captured native-fs by `tests/golden/capture/capture_cp.py`): the weight and reconstructed GOIs are
**bit-exact**, and `uu` matches to **~3e-12** (BLAS-accumulated, asserted rtol 1e-6)
on all valid frames.

- **GIF5 Option B, as decided.** A frame whose nonzero-weight support `< nar+1` is
  flagged (`ClosedPhaseResult.frame_valid`), but the solve still runs — `lpc_covar`
  returns the min-norm solution, so the flow stays **finite** (never a signal NaN).
  The per-frame flag maps to per-cycle NaN downstream (`invalid_cycle_mask` +
  `apply_cycle_mask`), the same seam VUV uses. On `vowel_glide_16k` the one
  rank-deficient frame (GIF3) is flagged and its `uu` **diverges** from the reference
  there (min-norm vs the reference's basic-solution artifact, both finite) — captured
  honestly, asserted as expected divergence, not a NaN.
- **Source finding — the reference driver's weight is a latent row/column bug.**
  the reference weighting constructor returns `w` as a `1×N` **row**; the reference weighted-LP driver
  passes it straight to the covariance solver, which errors on a column signal
  (`sc = s(cs).*w(cs)` broadcasts to `N×N`). fs-independent — the driver's `cp` path
  does not run as written. The capture passes `w(:)` (the intended usage; the AR is
  sensible and matches voicekit). Reproduced as a capture-script note, not in the
  port (voicekit's per-frame solve is orientation-agnostic).
- **Source finding — the de-emphasis IIR smears the GIF5 divergence forward.** `uu`'s
  rank-deficient-frame divergence is **local** (an FIR inverse filter confines it to
  that frame's output span), but `u = deemph(uu)` is a causal IIR (5 Hz pole ≈ 0.998,
  slow decay), so `u` matches the reference only **up to** the first invalid frame and
  is IIR-tainted after. The per-frame→per-cycle mask (overlap rule) maps the *directly*
  corrupted `uu` span; the forward `u` taint is a characterized limitation, not chased
  by the mask (the golden test asserts `u` parity only up to the first invalid frame).
- **Between-spurt boundary (confirmed from source).** The `cp` mask's between-spurt
  line `w(max(1,gci-cpDelay):gci)=0` is **inclusive of the GCI**; the mask is built
  1-based-internally so this `+1` is automatic, and the whole mask is bit-exact vs
  the reference weighting constructor.
- **GIF5 completed: the feature mask covers the FORWARD smear, because features read
  `u`.** Established from the code (not assumed): `prepare_cycles` builds `useg = u/fs`
  and the amplitude/spectral/timing features are `u`-derived (`prep.py`, `flow.py:54`,
  `spectral.py:90`); only `mfdr` reads `uu` (`flow.py:53`), `naq` both. Since features
  read `u`, and `u`'s IIR taints from the first rank-deficient frame's start to the end
  (above), the **local `uu`-span mask is a silent under-mask** — every cycle after the
  invalid frame would emit a finite-but-wrong `u`-feature. So
  `voicekit.features.apply_closed_phase_mask` masks **every cycle from the first invalid
  frame onward** (the forward extent), NaN via the same `apply_cycle_mask` seam VUV/O1==0
  use, with a `reason` array. This is correctness, not pessimism; there is no grounded
  sub-magnitude cutoff (the 0.998 pole decays too slowly to fit one — rule 1), so the
  full forward extent is masked. `invalid_cycle_mask` remains the honest *local* `uu`
  primitive, documented as not-for-`u`-consumers. A consumption pin test fails if a
  refactor routes a `u`-feature through `uu` (which would invalidate the extent).
- **Status:** closed-phase COMPLETE end-to-end — detection → weighter → flow → features
  with rank-deficient cycles honestly NaN'd, a weighting-function-plus-config interface
  item 9's harness consumes. AME and the two Gaussian variants are the next methods on
  the same `lpc_covar` seam (continuous weights — where the `W^2` convention actually
  bites, unlike `cp`'s 0/1).

### GIF9. Shared weighted-LP core extracted: the method-independent solve is single-sourced; only the weight vector changes per method

Landed 2026-07-22 (commit `cfbcdad`) as a behaviour-preserving refactor ahead of the
three continuous-weight methods, and proven a no-op rather than argued one.

- **The seam.** Every step-8 method is the same solve under a different per-sample weight
  (GIF8): a per-frame AR on the pre-emphasised signal under the method's weight, inverse
  filter the original signal, de-emphasise. `gif/weighted_lp.py` is that core —
  `_weighted_lp_solve(sp, fs, weight, *, preemph_hz, frame_len_s, frame_hop_s) ->
  WeightedLpResult` — holding the frame grid, pre-emphasis, the GIF1 `W^2` squaring, the
  per-frame `lpc_covar(dc_offset)`, the GIF5 validity rule (`count_nonzero(w[nar:]) >=
  nar+1`), the inverse filter and de-emphasis. Each method is a thin weight-construction
  wrapper: build weight → call the core.
- **Result-type split (no `goi` on the shared type).** `WeightedLpResult` carries
  `u, uu, weight, frame_starts, frame_valid` — all method-independent. `ClosedPhaseResult`
  **extends** it, adding cp's `goi` (the reference GOI-selection output the 0/1 mask
  needs, GIF6); the three continuous methods are gci-only and return the bare
  `WeightedLpResult`. An optional-`goi`-on-the-shared-type was rejected as exactly the
  coupling the split exists to prevent.
- **Mask made method-general.** `apply_closed_phase_mask` → `apply_invalid_frame_mask`,
  retyped (with `invalid_cycle_mask`) to `WeightedLpResult`: both read only
  `frame_valid` / `frame_starts` / `uu.size`, produced identically for all four methods,
  so the cp-specific name no longer fit.
- **Framing constants single-sourced.** `_PREEMPH_HZ = 5.0`, `_FRAME_LEN_S = 32e-3`,
  `_FRAME_HOP_S = 16e-3` hoisted to `weighted_lp` and referenced by every method config.
  Genuine coupling (all methods share the grid / pre-emphasis and must change together),
  and **bit-identical** to the former `ClosedPhaseConfig` literals — verified same
  IEEE-754 pattern — so the guard proves *preservation*, not a both-paths-read-the-new-value
  coincidence. `features/flow_derivation`'s `f_preemph = 10` (the IAIF de-emphasis) is a
  **different** constant, coincidence not coupling, deliberately left out of the hoist.
- **Guard-test-first (preservation proven, not asserted).** The committed cp `.cp.npz`
  goldens reproduce **bit-identical** through the refactored path; the forward-smear mask
  assertions (`test_gif_feature_mask`), the cycle-mask mapping (`test_gif_cycle_mask`) and
  the glide rank-deficient-frame assertion (`invalid.size == 1`) stayed green with their
  assertions **untouched** (imports / types only). Bisect-clean: green with the
  capture-gate files removed (343 tests), so the extraction needs no method code —
  provable by cp alone.
- **Status:** landed, no behaviour change. The four methods now share one solve; the
  bisect log carries this as the no-op-by-design commit.

### GIF10. GIF1 confirmed live for the first time: continuous weights make W-vs-W² a real negative control (two-sided capture)

Captured 2026-07-22 (commit `409007e`) — the first exercise of the GIF1 convention by a
weight that is not 0/1.

- **Why it had never really been tested.** cp's 0/1 mask makes `W^2 == W` (idempotent),
  so GIF1 was a structural no-op for it and cp's golden could only be one-sided (positive:
  the flow matches). The three continuous methods have `W^2 != W`, so `lpc_covar(W)` and
  `lpc_covar(W^2)` solve genuinely different least-squares problems — a negative control
  finally exists, and dropping it would be the scale-invariance zero-evidence pass GIF1
  documents.
- **Two-sided, both sides against the reference AR** (the reference weighting constructor
  → `v_lpccovar`, native fs, all frames, via `capture_gif_weights`):
  - POSITIVE: `lpc_covar(weights = W**2)` reproduces the reference AR on every frame.
  - NEGATIVE (control): `lpc_covar(weights = W)` diverges by O(1) — max `|ΔAR|` in
    `[0.70, 3.9]` across methods / fixtures — asserted on the probe frame so the test
    fails if `W` ever starts matching (a degenerate frame the positive side could not
    distinguish).
- **The mechanism, pinned from source.** `v_lpccovar` applies the weight to the residuals
  (`dm.*w`, `s.*w`, then `dm\sc`), so `W^2` emerges in the normal equations naturally — it
  does **not** pre-square the vector. `lpc_covar` takes `sqrt(weights)`. So reproducing
  reference weight `W` means passing `weights = W**2`: weight-on-residuals, not
  squaring-the-vector.
- **Positive-side tolerance is order-scaled evidence, not a picked number.** cp never
  asserted the bare AR solve — its golden persists only weight / goi / flow, so there is
  NO precedent for the AR tolerance. The `atol = 1e-10` stands on its own: the deviation
  is ~3e-12 at order-16 (16 k) and ~3.5e-13 at order-8 (8 k) — it *tracks* problem size,
  the signature of numpy-SVD-vs-MATLAB-QR accumulation on identical inputs, not a flat
  floor. Named in-test.
- **Synthetic decomposition (the second mechanism).** The reference is the SOLE oracle
  for these methods (no COVAREP / independent weighted-LP cross-check), so a golden-master
  pass proves "matches the reference," not "computes what we expect." A constructed rgauss
  cycle asserts the DECOMPOSITION — hand-verified weight values, and that `W^2` enters the
  normal equations via the reference's own `dm.*w` mechanism reproduced independently in
  numpy — on a deliberately non-fittable signal (four components at order 4; an
  exactly-fittable signal would zero the residual and blind the probe, the second GIF1
  blinding mechanism).
- **Status:** GIF1 confirmed live and two-sided; every continuous-weight method routes
  through the `W^2` seam, and the capture is the arbiter for all three.

### GIF11. The three continuous-weight methods landed (AME, rgauss, agauss): weight construction, params, flow parity, the migration discipline

Landed 2026-07-22/23 as three commits (`0fa1356` AME, `1d798f1` rgauss, `ad41344` agauss),
each a wrapper over the GIF9 core.

- **Weight constructions** (from the reference weighting constructor; `-0.5`-present, GIF4):
  - AME (Alku): attenuate the main-excitation region to a positive floor `d`, positioned
    `round(PQ·DQ·T)` before each GCI, width `round(DQ·T)`, with `rlen`-sample ramps.
  - rgauss (Zalazar, symmetric): `w = 1 - Σ κ·exp(-½(n-gci)²/σ²)`.
  - agauss (Zalazar, asymmetric): a half-Gaussian each side of the GCI — narrow after
    (`σ1 = α·N0`), wide before (`σ2 = r·σ1`) — under a `max(0, 1-gg)` clamp (GIF12).
- **Params, Rule-1 pinned from the reference parameter file, not fitted.** AME `d=0.01,
  DQ=0.4, PQ=0.8, rlen=3, minF0=50`; rgauss `κ=0.9, σ=√50`; agauss `κ=0.99, α=0.1, r=2,
  minF0=50`. Each on a typed frozen config; framing references the GIF9 shared constants.
- **Two `maxSamplesPerCycle` formulas — coincidence, not coupling.** AME uses
  `ceil(fs/minF0)`; agauss uses `0.5·ceil(fs/minF0)`. They differ and are commented at
  each site as deliberately distinct, so no later tidy-up single-sources them.
- **Migration discipline.** Each weight fn was migrated **verbatim** from the capture-gate
  test into its production module, params sourced from the config with defaults equal to
  the former literals — a relocation, not a reimplementation. The GIF10 convention test
  switched inline copy → production import with its assertion **untouched**, reproducing
  the captured weight: AME bit-exact (exact arithmetic), rgauss/agauss machine-eps (`exp`
  last-ULP, MATLAB vs numpy). The rgauss production is in fact *closer* than the inline
  copy (1.1e-16 vs 2.2e-16): it forms `σ2 = σ²` from `σ=√50` as the reference does, not
  the inline literal `50.0`. After agauss, no inline weight copy remains.
- **Flow parity (the new end-to-end golden).** GIF10 pinned the weight and the AR; the
  method commits add `u`/`uu` through the inverse filter + de-emphasis (`capture_gif_flow`,
  reusing cp's inverse-filter path so the `lpcifilt`-vs-`v_lpcifilt` choice stays settled
  by cp). Asserted at `rtol=1e-6, atol=1e-9` (the cp/GIF8 accumulation reason); observed
  abs deviation ≤ 1.2e-12 across 16 k and 8 k.
- **gci-only, and 8 k is clean.** All three read `gci` only; the reference weighting
  constructor's `any(goi-gci<=0)` guard needs a valid `goi` passed but the branches never
  read it, so the voicekit API omits `goi`. Unlike cp's F1 8 k exclusion (a live-IAIF
  limitation), these methods do not route through IAIF, so 8 k flow parity is captured and
  asserted — measured clean, not dropped.
- **Status:** three methods complete through flow; features close transitively (GIF13).

### GIF12. agauss support is full BY MEASUREMENT, not construction: its clamp can zero support, so GIF5 is live-but-unreached for agauss

Established 2026-07-23 at the agauss commit (`ad41344`) by re-measurement on the fixtures,
framed precisely so the distinction is not overstated.

- **The distinction is provenance, not observed behaviour.** AME (positive floor `d>0`)
  and rgauss (`min w ≈ 1-κ = 0.1 > 0`) have full support **by construction** — their
  weights can never zero support, on any input. agauss's `max(0, 1-gg)` clamp **can**
  produce hard zeros where summed neighbour notches drive `gg > 1`, so whether a frame goes
  rank-deficient is a question answered by measurement.
- **Re-measured on the fixtures (fresh, not a survey citation).** The clamp zeros
  **3 / 2 / 0** samples on `vowel_f0100_16k` / `vowel_glide_16k` / `vowel_f0120_8k`; the
  minimum per-frame nonzero support is **510 / 511 / 257** against `nar+1 = 17 / 17 / 9`.
  So **zero rank-deficient frames** — `frame_valid` is all-true on every fixture, but as a
  *measured* fact, not a guarantee.
- **Mask status, stated exactly.** For agauss the invalid-frame mask is **live** (its clamp
  can drop support, unlike AME/rgauss where it is unreachable-by-construction) but
  **unreached** on current fixtures. It is NOT "exercised": glide/cp remains the only
  fixture that drives `frame_valid = False` (GIF8). Corpus data with pathological GCI
  spacing could clamp harder and reopen the GIF5 rank-deficiency path for agauss — a
  reopen-with-evidence, like GIF2's deferred alternative.
- **Clamp handling is identical on both sides.** The clamp lives inside the weight fn, so
  the reference capture and voicekit solve on the same clamped weight; the flow *at the
  clamped samples* matches at the flow tolerance (asserted), so the few zeros are not a
  divergence source.
- **Status:** agauss full support measured (not constructed) on all fixtures; the GIF5 path
  is live-but-unreached, reopenable on corpus evidence. Cross-ref GIF5, GIF11.

### GIF13. Step-8 features close transitively: the composition seam is method-blind, so parity-validated flow validates each method's feature path

Decided 2026-07-23 (commit `26fcc7d`) — the same composition argument step 6 used to close
its orchestration seam (the "J4" join) without a full-pipeline golden.

- **The seam is airtight-transitive (from the signatures).** `extract_voice_features(u,
  uu, fs, gci, config)` consumes only method-independent inputs — `u`/`uu` (parity-
  validated flow), `fs`, the detection `gci` (not the method), and a `FeaturesConfig`
  (NOT the method's config) — so it structurally cannot distinguish which method produced
  the flow. `apply_invalid_frame_mask(feats, gci, result)` reads only the shared-core
  `WeightedLpResult` fields (`frame_valid`, `frame_starts`, `uu.size`), produced
  identically for all four methods. Nothing method-specific crosses either seam.
- **Three links, each already pinned.** (1) Flow parity — the three methods' `u`/`uu` match
  the reference at machine-eps (GIF11). (2) The extractor — validated on captured flow at
  machine-eps (step 6), and method-blind by the above, so it validates on any
  parity-matched flow. (3) The mask — validated by glide/cp's live rank-deficient frame
  (GIF8, the forward-smear extent). Transitively, each method's feature path is validated.
- **What transitivity does NOT cover, and the smoke test does.** Transitivity validates
  each link *assuming* the pieces connect; it does not prove they connect. One composed
  smoke test per method drives `method_gif → u/uu → extract_voice_features →
  apply_invalid_frame_mask → VoiceFeatures` and asserts a well-formed result (finite flow
  in, every field shaped `(gci.size,)`, `reason` all `"valid"` since these methods have no
  rank-deficient frame, mask a no-op). It proves the seam CONNECTS — no
  attribute/shape/type mismatch — nothing numerical.
- **No full per-method feature golden (deliberate).** That would re-validate the three
  already-pinned links in composition — the redundancy step 6 declined. No production
  change was needed: the wiring already composes.
- **Status:** step 8 closed. Four weighted-LP GIF methods over one core (closed-phase, AME,
  rgauss, agauss), each with flow parity, GIF1 two-sided validation (the three continuous),
  transitively-validated features, and a common `(signal, fs, gci, *, config)` interface
  ready for item 9's scoring harness.

## Step 9 (GCI/GOI scoring harness) — forward findings

### SCORE1. The between-segment false-alarm exclusion is underdetermined by the paper — an open question, recorded not resolved

Recorded 2026-07-23 at the methodology gate, before any scorer code. The YAGA metric
set (ID/miss/FA + FAT, σ + bias μ, GOI) was ratified as the target; the FA-exclusion
rule that separates FA rate from FAT is the one piece the paper leaves vague, so it is
logged here as an open question and the scorer is built with the exclusion structurally
absent (not stubbed).

- **The rule, verbatim** (Thomas et al. 2012, YAGA, §V-A, p. 89): *"False alarms are
  not counted if they occur between voiced segments separated by more than 3 ms."* The
  companion metric, same paragraph: *"False Alarm Total (FAT), measures all false alarms
  as a proportion of total candidates, including those between voiced segments. This
  helps to assess the quality of voicing detection and the suppression of multiple false
  alarms within one reference cycle."* Fig. 7 (the outcome-characterisation figure) does
  **not** illustrate this rule — it is structurally identical to DYPSA's Fig. 2 (two
  instant trains, the four cycle outcomes), with no voiced-segment boundaries and no
  3 ms marker. The rule lives only in that one prose sentence.

- **Ruled out — the naive reading.** "3 ms" is **not** the gap threshold between
  adjacent reference GCIs: 3 ms ≈ 333 Hz is shorter than any plausible pitch period, so
  under that reading every inter-cycle gap would exceed it and every cycle boundary would
  be a segment break. Dimensionally incoherent; discarded.

- **Ratified constraint — segmentation is reference-derived, never VUV-derived.** Where
  the exclusion rests on a voiced/unvoiced segmentation of the signal, that segmentation
  must come from the reference, **not** from the algorithm's own voicing detector. The
  text forces this: FAT exists to *"assess the quality of voicing detection,"* and you
  cannot assess a detector using its own output as the exclusion boundary — that is
  circular, and it would make FA rate tunable through a detector parameter (a rule-1 back
  door). This constraint is binding.

- **Underdetermined — two axes, neither resolved here.**
  (i) *What quantity the 3 ms measures.* No reading is established from the text. At
  least two survive it, structurally different:
    - an **edge-guard** band around reference voiced-segment boundaries — a
      between-segment candidate farther than 3 ms from the nearest voiced region is
      dropped (this makes the sentence sane, but note it re-introduces a *tolerance
      window*, the very thing the gate found this methodology otherwise lacks);
    - a gap **within the estimated GCI train** — a run of estimated GCIs with an
      internal gap exceeding 3 ms constitutes two segments, and false alarms falling in
      that gap are dropped.
    Neither is asserted correct; that two survive is the point.
  (ii) *The reference-segment-break threshold* — the pitch-scale gap in the reference
    GCI train that delimits one voiced segment from the next (distinct from the 3 ms,
    which the naive reading already ruled out as this threshold). The paper fixes no
    value.

- **Inert on OpenGlot; does not block steps 2–3.** OpenGlot is sustained voiced vowels
  with no unvoiced gaps, so there are no between-segment regions and the exclusion never
  fires. The scorer and its synthetic validation, and the first corpus run, are all
  unaffected. FAT — whose defining clause *is* the between-segment inclusion, and whose
  per-candidate numerator ("all false alarms": k or k−1 in a k-detection FA cycle?) is
  itself unspecified — is deferred with the exclusion rather than reconstructed.

- **Must be settled before APLAWD scoring.** APLAWD is running speech with genuine
  unvoiced gaps; there the exclusion is load-bearing and FA rate cannot be computed
  faithfully until both axes above are settled. Settle it (with human ratification, and
  a further ledger entry recording the chosen reading and rationale) at the APLAWD gate,
  not in implementation.

- **What the pins guard (and what they do not).** The absence is pinned at the API
  surface only — the `ScoreConfig` and `InstantScore` field sets and `fat`'s `None`
  type (a new parameter, a parallel field, or a retype each break a test). A hardcoded
  `3.0` buried in scoring logic is caught by no pin; whoever settles this before APLAWD
  must check for one by reading the code, not trust the tests.

- **Status:** OPEN. Scorer ships fully-determined metrics only (ID/miss/FA per-cycle,
  σ, bias μ, per-cycle decomposition, GOI via the two-tier signature); the
  between-segment exclusion and FAT are structurally absent, flagged in the result and
  the tests so their absence is visible, not silent.

### OG-GCI. The OpenGlot GCI reference: analytic tₑ for R1, −dUg/dt-peak for R2; the peak-pick operator is a systematically-early estimator whose magnitude is R1-specific and does not transfer

Recorded 2026-07-23 at the OpenGlot gate, before any harness code. OpenGlot ships **no
GCI annotations** — it is a glottal-inverse-filtering benchmark whose ground truth is the
glottal-flow *waveform* (Alku et al. 2019: the flow Ug(t) is *"the primary sound source
for vowels"*; Table 4 parametrises reference Ug/Ag by open/closing quotients, never an
instant). Every reference GCI we score against is therefore constructed by us. This entry
fixes how.

- **R1 reference = analytic tₑ.** R1 is LF-generated; tₑ = (1+Rk)/(2·Rg·f₀) is the instant
  of maximum negative flow derivative, exact per pulse from (f₀, phonation mode).
  Reimplemented from Fant/Liljencrants/Lin; OpenGlot's shipped `.m` used only as the
  reference for phonation-mode parameter values. The reference is the analytic instant
  placed in the file's sample frame — **not** a peak-pick of the flow channel.

- **R2 reference = −dUg/dt peak on the glottal-flow channel** (ratified). Area-zero-crossing
  is the **rejected alternative**, recorded with its predicted disagreement stated a priori:
  flow-derivative peak precedes area closure, so **area-zero lags the adopted instant by
  ~0.2–0.8 ms** (a fraction of the closing phase; tens of samples at 44.1 kHz). Grounds for
  flow: it is the acoustic excitation instant a GCI detector responds to, it matches R1's tₑ
  definition, and the paper privileges Ug as the sound source. The choice is a priori; the
  ~0.2–0.8 ms difference is to be *measured and reported* once R2 runs, never used to select
  the channel.

- **Baseline operator (fixed): central-difference derivative + discrete argmin per cycle, no
  sub-sample refinement.** (If sub-sample instants are later wanted, the fixed method is
  parabolic interpolation about the argmin — a separate, separately-ratified operator, not
  the baseline.)

- **The operator is a systematically *early* estimator of the true instant.** Mechanism: the
  discrete argmin of an *asymmetric* extremum is biased toward its gentle flank; the LF
  closure is gentle-approach / fast-return, so the sampled minimum lands before tₑ.
  Sub-sample refinement would remove quantisation scatter but not this bias (a symmetric
  parabola on an asymmetric cusp leaves the displacement).

- **R1 quantifies this — for R1, at 8 kHz — and the number stays there.** Measured
  operator−tₑ on shipped R1 (48 k→8 k as generated): all-mode mean **−0.88 sample
  (−0.110 ms)**, every condition early. Decomposed against a direct-sample control:
  **~−0.59 sample operator-intrinsic + ~−0.29 sample from OpenGlot's specific 48 k→8 k
  anti-alias filter.** Per mode (8 kHz): normal −1.10, breathy −1.03, creaky −0.78,
  whispery −0.61 sample — largest for the sharpest, most-asymmetric closures.

- **The magnitude does NOT transfer to R2; only the mechanism does.** R2 has no 48 k→8 k
  resample (so the −0.29 component is absent), and R2's flow is a kinematic-vocal-fold
  waveform, not an LF pulse — a *different* closure asymmetry. The R1 magnitude already
  varies ~2× across LF modes alone, proving it is shape-specific. Therefore R2 inherits a
  **named, unquantified early contribution to μ**: known in direction and cause, unmeasured
  in size because R2 has no truth to measure against. **Never estimated by fitting, never
  corrected.** Writing an R1 number into R2's μ would give it authority over an object it
  was not measured on.

- **Does not affect R1 scope.** R1's scored reference is analytic tₑ, so the operator bias
  never enters R1's σ/μ. The R1 operator run is diagnostic only.

- **Status:** reference definitions RATIFIED (R1 analytic tₑ; R2 −dUg/dt, area rejected).
  Operator-bias magnitude quantified for R1/8 kHz; for R2 it is a named-but-unquantified μ
  term by construction. No 3 ms / segmentation interaction (R1/R2 are sustained voiced
  vowels; cf. SCORE1).

### OG-GOI. The OpenGlot GOI reference: R1's t_o is a synthesis seam (no GOI accuracy scored there); R2 flow-onset carries the OG-GCI bias, and its reference-accurate flag is a decision, not a property

Recorded 2026-07-23 at the OpenGlot gate, before any harness code. As with GCIs, OpenGlot
ships no GOI annotations; the reference is constructed. Unlike OG-GCI, this entry does
**not** have a strong-authority analytic instant to offer for R1 — that asymmetry is the
point of the entry.

- **R1's t_o is the LF period boundary — a synthesis seam, not an opening event.** The
  shipped LF synthesis has **no closed phase**: `synthFrame.m` concatenates pulses with
  Te+Tb = 1/f₀, so the flow leaves zero only *instantaneously* at the pulse-to-pulse
  boundary (U(0)=0 analytically, but momentarily — it does not rest at zero). The absence of
  a closed phase establishes the **absence of a physical opening instant to recover**, not
  the presence of one. R1's t_o is therefore a property of the concatenation, with no
  glottal event behind it.

- **Consequence — R1 scores no GOI accuracy/bias.** Scoring σ/μ against t_o would measure
  agreement with a synthesis boundary, and is **not** evidence about GOI detection on speech
  with a real closed phase; it could penalise a detector that correctly finds no distinct
  opening — evidence of the wrong sign, not merely weak evidence. This is a materially weaker
  object than OG-GCI's analytic tₑ and must not sit in the same register of authority. R1 GOI
  *hit rate* is in any case identical to GCI hit rate (shared cycle logic) and adds no
  independent information. **Decision: R1 contributes GCI accuracy only; GOI accuracy/bias is
  scored on R2, not R1.**

- **R2 reference = glottal-flow opening on the flow channel**, consistent with the
  flow-primary choice in OG-GCI, where the kinematic vocal-fold model produces a real
  (adduction-dependent) closed phase and thus a physical opening. Area-onset is the rejected
  alternative. Any derivative-based opening estimator inherits the asymmetric-extremum
  mechanism of OG-GCI: early, cause and direction known, magnitude unquantified on R2, never
  fitted or corrected.

- **The reference-accurate flag, split R1 from R2:**
  - *R1 GCI:* analytic tₑ is exact, so `reference_accurate` all-True is a genuine **property**
    of the data.
  - *R2 (GCI and GOI):* the reference is the peak-pick operator, which OG-GCI establishes as
    systematically early by an **unquantified** amount. A reference carrying an unquantified
    bias is not accurate — it is uniformly **treated** as accurate. YAGA's flag means "the
    reference is trustworthy for this cycle," so setting it all-True on R2 is a **decision to
    score σ/μ against a biased reference**, taken because **no per-cycle basis exists to flag
    any cycle as worse than another**, not a property of the data. **R2's σ/μ therefore carry
    the OG-GCI bias term wholesale.**

- **Carry-forward (to be restated when the R2 driver is specified).** With R1 contributing
  GCI accuracy only, R2 is the **sole source of GOI accuracy in the entire synthetic phase**,
  scored against a reference with an unquantified bias and a reference-accurate flag set
  all-True by decision. No known-answer test validates GOI accuracy anywhere in the sequence:
  the "validate the instrument on a known answer before trusting it on an unknown" discipline
  holds for GCI (R1 analytic tₑ) but **not** for GOI. R2's GOI σ/μ do not have the same
  standing as its GCI σ/μ and must not be reported as though they do.

- **Status:** RATIFIED. R1: GCI accuracy only, no GOI accuracy (t_o is a synthesis seam).
  R2: GOI accuracy/bias scored against flow-onset, reference-accurate flag all-True by
  decision (reason recorded), σ/μ inheriting the OG-GCI operator bias. See OG-GCI.
