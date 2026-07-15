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

Beyond these five (which are all port-vs-reference), a trailing **Step 7 (VUV) —
forward findings** section records watch-items surfaced while designing the
in-progress voicing milestone. Those are design findings for an as-yet-unbuilt
component, not reproduction facts.

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

### 6. NAQ silent IEEE division when `dpeak == 0`

- **Where:** `voicekit.features.flow` (`flow_statistics`), the `naq` division
  `fac / (dpeak * t_time)`; reference `extractVoiceFeatures.m`, the per-cycle `else`
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
  reference `extractVoiceFeatures.m`, the per-cycle loop. Subsumes the flow group's
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

- **Where:** `voicekit.features.spectral` (`spectral_params`, the guard); reference
  `extractVoiceFeatures.m`, `specParam`.
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
  (validation-phase, filed not chased):** `iaif.m` note 6 recommends `p=8; g=2; r=8`
  at 8 kHz, but `dypsagoi.m` calls `iaif(s, fs, 20, 4, 20, 1)` at **every** rate — a
  20th-order vocal-tract LPC over a 4 kHz band at 8 kHz. That over-ordering is a
  plausible ill-conditioning route to the NaN residual tail this fixture works around,
  which would make F1 a *reference-configuration* artifact rather than a fundamental
  8 kHz failure. The port faithfully mirrors dypsagoi's 20/4/20 at all rates
  (`YagaConfig._default_iaif_config`); revisiting the 8 kHz order is validation-phase
  work, not this milestone's.

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

### V2. QOQ divides a duration by an index: `qoq = (C2-O2)/O2`

- **Where:** `voicekit.features.timing` (`timing_statistics`); reference
  `extractVoiceFeatures.m`, the per-cycle loop.
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

- **Where:** `voicekit.features.spectral` (`spectral_statistics`); reference
  `extractVoiceFeatures.m`, the `specParam` call site.
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

- **Where:** `voicekit.features.spectral` (`spectral_params`); reference
  `extractVoiceFeatures.m`, `specParam`.
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
(`vuvMeasurements`: Nz, Es, C1, alp1, Ep) are a *deterministic* function of the
signal — no RNG — so they **are** golden-masterable, exactly like steps 1–6. The
features are therefore captured against a MATLAB oracle
(`tests/synthetic/*.vuvfeat.npz`, regenerable via `capture_vuv_features.py`) and
validated bit-exact / machine-ε / BLAS-ε (`test_vuv_features_parity`). This
re-scoping is what made the parity capture possible at all — a later reader
wondering why a "define-the-target" milestone carries a golden-master should read
it as: **features capture-and-match, decision define-the-target.**

### VUV1. Binary output does not imply a single-stage classifier — the silence pre-gate is a deliberate design choice

The step-7 output label is binary (voiced / non-voiced), but that is the *output*
domain, not the classifier's internal structure. In true silence or near-floor
noise the periodicity features (`C1`, `Ep`) are computed on noise and cannot
distinguish "unvoiced speech" from "no speech at all," so the detector plausibly
needs an internal energy/silence pre-gate feeding the voiced/unvoiced decision.

- **Watch:** an energy-based pre-gate in front of an energy-driven main decision
  is an energy classifier in disguise — it re-enters the *floor-fixture trap* (a
  detector that passes the clean S/V/U/V/S fixture on energy alone while failing
  the hard cases the detector exists for) through the front door. The silence
  stage must be designed deliberately at the sub-gate, against a discriminating
  fixture, not bolted on.
- **Threshold provenance (established for periodicity only; open for the pre-gate).**
  The decision-rule sub-gate settled the *periodicity* threshold's provenance: the
  analytic noise null (normalized autocorrelation std ≈ 1/√N at the locked grid's
  frame length N), with a dimensionless significance knob in `VuvConfig` and the
  concrete number derived at runtime from knob + N — structurally out-of-sample
  from D1/D2/D3, derived from the generic null and **never** measured off the
  fixture's noise regions. **That provenance covers the periodicity separator
  only.** If the rule carries a silence/energy pre-gate, its threshold requires
  its **own** separately-named, out-of-sample calibration source, re-confirmed
  when it is designed. The acute reason: an energy pre-gate is an *energy*
  threshold, and energy is the very feature **D1 was constructed to defeat** — so
  calibrating it by reference to D1/D2/D3 is the floor-fixture-trap circularity in
  its most direct form. The pre-gate must not acquire a threshold later without
  its provenance re-confirmed out-of-sample. Flag, not design.
- **Status:** open design finding for the detector sub-gate.

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

The voicing frame grid is locked at **32 ms frames / 10 ms hop** (the Atal-Rabiner
voicing-analysis standard), in `VoicingGrid` (`src/voicekit/vuv/grid.py`) — its own
config, **not** derived from `IaifConfig`. @16 kHz: `frame_len` 512, `hop` 160,
guard band **W = 512/2 + 160/2 = 336** samples; @8 kHz: 256 / 80 / 168.

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
  ([vuvMeasurements.m:89](inriaGIF/vus/vuvMeasurements.m)). By MATLAB semantics
  (`s` is `N×1` since `sp=sp(:)`; `s(1)*s0` is a **scalar**; `(N-1)×1 vector +
  scalar` broadcasts the scalar), the **numerator** boundary term `s(1)*s0` enters
  **N-1 times**: `Σ(s(2:end).*s(1:end-1)) + (N-1)·s(1)·s0`. The **denominator**'s
  `[s0; s(1:end-1)]` is an `N×1` vector with `s0` as **one element**, so its `s0`
  enters **once**. That numerator-broadcast/denominator-once asymmetry breaks
  Cauchy-Schwarz and is exactly why C1 is **unbounded above** (>1; 1.448 measured
  on D3). The author almost certainly *intended* add-once (a proper normalized
  cross-correlation, bounded [-1,1]), but the code broadcasts — reproduced
  faithfully (the parity capture matches MATLAB only if we broadcast), **not
  corrected to add-once**. The floor verdict (C1 separates) holds under *either*
  reading; only the unboundedness (and thus VUV8) depends on the broadcast.
- **Mitigation (landed):** C1's fidelity gets the strongest verification of the
  five — hand-computed synthetic-known-value tests isolating the `s0` reach, the
  broadcast, the denominator (`tests/test_vuv_features.py`), **and** the
  `vuvMeasurements` parity capture (`tests/test_vuv_features_parity.py`, oracle
  `tests/synthetic/*.vuvfeat.npz`).
- **What the parity capture proved (VUV7 closed):**
  - **C1's broadcast reading is confirmed BIT-EXACT by the oracle** (0.0 abs error
    on all four fixtures). The reproduced numerator/denominator `s0` asymmetry is
    what MATLAB computes; a wrong-but-separating C1 — the hole the floor cannot
    cover — is now caught by parity.
  - **The capture caught the `alp1`/`Ep` DC-offset gap the synthetic tests
    structurally could not.** Commit 2 read `alp1`/`Ep` from plain covariance LPC;
    the oracle showed them off by ~1.3e-2 / ~5.7e-2, tracing to `vuvMeasurements`'s
    three-output `[ar,e,dc]=lpccovar` (DC-offset fit). Routing through
    `dc_offset=True` (commit 3b) brought them to BLAS-ε (≤3.4e-12 / ≤3.8e-8). This
    is the concrete evidence the capture was **required**, not optional: the
    synthetic tests never compared `alp1`/`Ep` to the reference, so only parity
    could find it.
- **Status:** **CLOSED.** C1 still gets the most scrutiny wherever touched; VUV8
  (below) remains open and independent.

### VUV8. BLOCKING: re-derive the C1 noise null for the reference formula before any threshold

The ratified threshold provenance (VUV1) is "normalized-autocorrelation std
≈ 1/√N over an aperiodic frame." That null is the **textbook bounded** autocorrelation's
([-1, 1]). The reference C1 — via the numerator-broadcast/denominator-once `s0`
asymmetry (VUV7) — is **unbounded above** (1.448 measured on D3), so the 1/√N
result does not apply. (Had the boundary term been add-once/symmetric, C1 would be
a bounded normalized cross-correlation and 1/√N would hold — so this BLOCKING item
exists *because of* the reproduced broadcast quirk, not despite it.)

- **BLOCKING precondition:** the decision-rule instantiation may **not** proceed
  until the noise null is **re-derived analytically for the reference C1's actual
  formula** (with the broadcast `s0` term).
- **The trap:** with 1/√N invalid, the pressure is to instead *measure* C1's
  distribution on D2/D3's noise regions — which is fitting-to-the-fixture, the exact
  circularity the gate order (fixture ratified before any threshold) exists to
  prevent. The out-of-sample guarantee survives only if the null is re-derived
  analytically for the real formula, never measured off the fixture.
- **Status:** BLOCKING on the decision-rule gate. Cross-ref VUV7 (same feature).

### VUV9. Coverage gap: no fixture exercises a rate where reference `ceil` ≠ VoicingGrid `round`

`vuvMeasurements` frames with `ceil(dur·fs)`; the locked `VoicingGrid` uses `round`.
They **coincide at 8 kHz and 16 kHz** (exact products), which is every current
fixture — so `round` wins with no conflict, and reference-`ceil` is reproduced
where coincident. But no fixture exercises a rate where `ceil ≠ round`, so that
divergence is **tracked, not assumed**. If such a rate is ever added, the feature
framing (`VoicingGrid.round`) and the reference (`ceil`) will diverge by a sample
and must be reconciled. Coverage-gap-style item, VUV-local. Status: open gap.
