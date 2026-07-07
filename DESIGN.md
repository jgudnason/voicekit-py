# voicekit-py — Design Document

## 1. Vision & scope

A comprehensive, open-source voice analysis toolbox in Python, implemented from
first principles. This is a from-scratch Python successor to a ~20-year line of
MATLAB research code (Imperial College DYPSA work, 2003–2009, later reworked and
distilled into `vsaTools`). The goal is a well-tested, cleanly licensed, publicly
redistributable library — not a port, but a rewrite grounded in the published
algorithm descriptions.

Why rewrite instead of port:
- The existing MATLAB code has no automated tests, inconsistent conventions,
  duplicated/diverging files, and at least one unresolved, self-documented bug
  (DYPSA's GOI post-processing step). Reference quirks the port reproduces for
  golden-master parity — including that GOI bug — are tracked in
  [REFERENCE_NOTES.md](REFERENCE_NOTES.md).
- Some of the existing code (`dypsagoi.m`) is bundled with Mike Brookes's
  GPL'd VOICEBOX toolbox and jointly copyrighted (Kounoudes/Gudnason/Naylor/
  Brookes). Reimplementing from the published algorithm rather than porting
  that source is what makes an Apache-2.0 release of an algorithm the
  author co-invented actually clean.
- Starting fresh is a chance to fix known design smells: global mutable
  parameter stores (`voicebox()`), copy-pasted files with silent numerical
  drift between copies, and zero test coverage.

## 2. Design principles

- **First-principles domain code.** The actual voice-science algorithms — LPC,
  IAIF, the DYPSA/YAGA dynamic program, weighted-LP GIF methods, LF-model
  fitting, feature extraction — are implemented here, not imported from a
  speech-processing library.
- **Numerical primitives are fine via numpy/scipy.** FFT, linear algebra,
  standard filtering, resampling — no need to reimplement these; the line is
  domain algorithms vs. numerical building blocks.
- **No global state.** Every algorithm takes an explicit, typed config object.
  No equivalent of MATLAB's global `voicebox()` parameter store.
- **Functional core, thin data containers.** Prefer pure functions over
  stateful classes. Use small frozen dataclasses to carry signals and results
  (e.g. `Signal`, `GciResult`, `VoiceFeatures`) rather than raw arrays/dicts or
  a heavyweight class hierarchy.
- **Every module cites its source.** Docstrings reference the paper(s) the
  algorithm comes from (e.g. Alku 1992 for IAIF; Naylor, Kounoudes, Gudnason &
  Brookes 2006/2007 for DYPSA).
- **No premature abstraction.** Build what the current milestone needs; don't
  generalize ahead of a second concrete use case.

## 3. Core data model

- `Signal`: a small frozen dataclass wrapping `samples: np.ndarray`,
  `fs: int`, and optional metadata (e.g. source filename). Passed explicitly
  everywhere rather than bare `(array, fs)` tuples, but with none of Aparat's
  operator-overloading/GUI-binding machinery.
- `Signal` is strictly mono, permanently: every downstream algorithm is
  defined on one channel, and a multichannel container would force each of
  them to reinterpret what stereo means. Multichannel files are handled at
  the I/O boundary instead — explicit channel selection in `read_wav`
  (added when first needed), never a silent downmix, since the two real
  stereo cases (conversation per channel vs. speech+laryngograph per
  channel) are structurally identical but semantically opposite. Which
  channel means what in a given corpus is per-dataset knowledge and lives
  in that corpus's adapter in `validation/`, not in `voicekit.io`.
- Per-algorithm result types (e.g. `GciResult` with `gci`, `goi`, candidate
  arrays; `VoiceFeatures` with `f0`, `naq`, `qoq`, `h1h2`, etc.) instead of
  positional-output tuples or MATLAB-style structs.
- Per-algorithm config dataclasses (the prior research code's per-method
  parameter structs were already a reasonable pattern — just made explicit
  and typed instead of switch-on-string).

## 4. Package layout

```
voicekit-py/
  src/voicekit/
    io/          # wav read/write, resampling
    lpc/         # autocorrelation (Levinson-Durbin) + weighted covariance LPC
    iaif/        # Iterative Adaptive Inverse Filtering
    yaga/        # DYPSA-derived GCI/GOI detection
    features/    # extractVoiceFeatures equivalent
    vuv/         # voiced/unvoiced detection
    gif/         # alternative weighted-LP GIF methods (cp, ame, gauss variants)
    lfmodel/     # Liljencrants-Fant model fitting
    pitch/       # F0 tracking (e.g. YIN)
    eval/        # accuracy metrics (hit rate, miss rate, timing error)
  tests/         # fast unit tests, small checked-in fixtures, run in CI
  validation/    # corpus-scale accuracy runs against OpenGlot / APLAWD
    openglot/
    aplawd/
    results/     # generated metrics/plots — gitignored
  data/
    fixtures/    # tiny synthetic wavs checked into git for unit tests
  pyproject.toml
  LICENSE        # Apache-2.0, verbatim text
  NOTICE         # copyright + attribution notices
  README.md
  DESIGN.md
```

`tests/` and `validation/` are deliberately separate:
- `tests/` is production-adjacent — fast, deterministic, small fixtures,
  runs on every push in CI.
- `validation/` is corpus-scale accuracy evaluation — slower, needs external
  datasets (OpenGlot, APLAWD) that aren't checked into git, and produces
  output artifacts (metrics, plots) that also aren't checked into git.

## 5. Testing & validation strategy

- **Unit tests** (`tests/`): one test module per `voicekit` module, using
  tiny synthetic fixtures committed under `data/fixtures/`. Fast, deterministic,
  run in CI on every push.
- **Golden-master tests** (during porting): capture reference outputs from
  the existing MATLAB implementations on fixed inputs, assert the Python port
  matches within numerical tolerance. Primary defense against silent porting
  bugs — the prior research code has a real example of exactly this failure
  mode: a missing `-0.5` factor in a Gaussian weighting exponent, introduced
  silently between two revisions of the same function.
- **Corpus validation** (`validation/`): accuracy evaluation against
  - **OpenGlot** — synthetic vowels with known ground truth (LF-model-derived
    GCIs), good for exact-accuracy checks with no annotation noise.
  - **APLAWD** — laryngograph-referenced real speech, the standard DYPSA-era
    evaluation corpus, needed for realistic hit-rate/miss-rate/false-alarm
    numbers.
  - Not part of default CI (needs external data, slower); run manually or on
    a separate scheduled workflow once data access is arranged.
  - External dataset location is configured via an env var (e.g.
    `VOICEKIT_DATA_DIR`) or a local, gitignored config file — never a
    hardcoded path. Expected directory layout documented in
    `validation/README.md`.
  - All generated output (metrics tables, plots, intermediate `.mat`/`.npz`
    dumps) goes under `validation/results/`, which is gitignored in full.

### Parity vs. evaluation, and the validation roadmap

Golden-master parity and corpus evaluation answer different questions, and the
project needs both. Parity asks "does the Python compute the same thing as the
reference MATLAB?" — bit-exact, one reference, and the primary porting defense.
It cannot, even in principle, tell us whether the algorithm is any *good*:
`dypsagoi.m` is an implementation with documented bugs (see `REFERENCE_NOTES.md`),
not ground truth, so a faithful port reproduces its misses and scores PASS while
saying nothing about detection quality. The evaluation methodology from the DYPSA
and YAGA papers — larynx-cycle hit rate, miss rate, false-alarm rate,
identification accuracy against a reference set of instants — is the only thing
that measures quality.

This gives two evaluation tracks, deliberately sequenced:

- **Track A — the scoring harness, against the reference implementation.** Score
  Python output against `dypsagoi.m` output run through the papers' hit/miss/FA
  machinery. On the golden-master fixtures this scores trivially perfect (the
  outputs are bit-identical by construction), which is exactly its value: it
  validates the *scoring instrument* against known-answer inputs before that
  instrument is pointed at real speech. Build it in `validation/`, sequenced
  fixtures → OpenGlot (clean synthetic ground truth, no data-format risk) →
  APLAWD. Best built once the `REFERENCE_NOTES.md` worklist is closer to complete
  (post-features, likely post-VUV), so the harness is designed against the full
  set of questions it must answer rather than retrofitted per milestone.
- **Track B — evaluation against real ground truth.** Score against
  EGG/laryngograph-derived reference GCIs/GOIs on APLAWD (and synthetic ground
  truth on OpenGlot), reproducing the papers' accuracy figures as far as is
  achievable. Needs Track A's harness plus the ground-truth data. Its decisive
  capability is the side-by-side comparison — Python-vs-reference and
  `dypsagoi.m`-vs-reference scored together — which isolates *port fidelity* from
  *algorithm quality*: identical scores prove the port is transparent (every miss
  is the algorithm's), divergence localizes a port artifact the golden master
  missed (a fixture-coverage gap; cf. the C-entries in `REFERENCE_NOTES.md`). This
  is the "is this error mine or the algorithm's?" decomposition, made decidable.

The `REFERENCE_NOTES.md` worklist is the experimental apparatus for this. Each
reproduced quirk is quarantined behind a named flag (e.g. `force_penultimate`,
`goi_postprocess`) precisely so that a correction is a controlled experiment: flip
one flag, hold the rest, measure the accuracy delta against ground truth under
Track B. The quarantine flags and coverage accounting are not just porting hygiene
— they are the pre-built methods for the development-phase papers that motivate
continued YAGA work once the faithful port is done.

## 6. Licensing & attribution

- Project-wide **Apache-2.0**, matching `vsaTools`, with public release as
  the explicit goal. LICENSE holds the verbatim license text; the copyright
  notice lives in NOTICE, per Apache convention.
- Every algorithm module's docstring cites the originating paper(s).
- Mike Brookes's VOICEBOX toolbox is gratefully acknowledged as the
  reference implementation many modules are checked against; where a module
  follows a specific VOICEBOX function, its docstring says so by name.
- A short note (in README and NOTICE) clarifying that domain algorithms are
  reimplemented from published descriptions rather than ported from the
  VOICEBOX source, even where the author is the same person and a named
  co-inventor of the algorithm.

## 7. Dependencies & performance

### Dependency policy — three tiers

- **Core runtime**: numpy and scipy only, with one candidate exception —
  `soundfile` (libsndfile) may be adopted for wav I/O the first time a real
  corpus file breaks `scipy.io.wavfile` (decades-old corpus files with odd
  headers make this likely). No speech-processing libraries (librosa,
  parselmouth, pysptk, and the like) in core — pulling one in would defeat
  the project's reason to exist.
- **Dev/test**: pytest, ruff, mypy, matplotlib (diagnostic plots). Test code
  may also use a library as an independent cross-check of a from-scratch
  implementation (e.g. PyWavelets to verify our SWT) without it becoming a
  runtime dependency.
- **Validation** (`validation/`, not shipped): deliberately liberal.
  Cross-checking against independent implementations (e.g. Praat via
  parselmouth for F0, other GCI detectors) catches bugs that golden-master
  tests cannot — golden masters only prove we match our own prior MATLAB,
  including its mistakes.

Borderline calls go to from-scratch when the code is part of the algorithm
rather than substrate. Concrete example: YAGA needs a 3-level stationary
wavelet transform (bior1.5) and scipy has no SWT — but it's ~30 lines of
FIR filtering with à-trous upsampled kernels and fixed published
coefficients, so we implement it rather than depend on PyWavelets.

### Performance — Python first, optimize with evidence

1. **Pure numpy first**, correctness locked by golden-master and corpus
   validation before any optimization. Optimizing against an unvalidated
   reference doubles the debugging surface (porting bug vs. optimization
   bug becomes undecidable). Research-scale batch work on modern hardware
   very likely needs no optimization at all.
2. **Profile on real corpus runs**, not guesses. Predicted hot spot: the
   N-best dynamic-programming recursion in YAGA (sequential over
   candidates, per-candidate cross-correlation costs); everything else is
   already vectorized linear algebra.
3. **Numba before C/C++** for any hot loop that profiling actually
   convicts: near-C speed, no build system, single readable source.
   Shipped as an optional extra (e.g. `voicekit[fast]`) so the core
   package stays pure Python and trivially installable.
4. **C/C++ (pybind11) only with a concrete product driver** — e.g. a
   real-time or embedded deliverable, or a standalone C library as a goal
   in itself. That is a product decision, not a performance patch.

The data-model choices above (pure functions, explicit typed configs,
arrays in/arrays out) are what keep a later numba or C++ port mechanical.
To preserve that, numerical kernels stay boring: no deep Python cleverness
inside the hot loops.

## 8. Tooling

- `pyproject.toml`, src-layout, installable via pip.
- `pytest` (+ `pytest-cov`) for unit tests.
- `ruff` for lint/format, `mypy` for type checking.
- GitHub Actions CI: unit tests + lint + type-check on every push/PR.
  Validation-suite runs are separate (manual trigger / local only), since
  they require external data and are too slow for per-push CI.

## 9. Roadmap

1. **Scaffolding** — repo layout, `pyproject.toml`, CI, LICENSE, empty
   package skeleton, fixture data directory.
2. **I/O & framing** — wav read/write, resampling, basic framing utilities.
3. **LPC** — two solvers, both from scratch:
   - *Autocorrelation method* (Levinson-Durbin recursion) — guaranteed-stable
     filters; the workhorse for IAIF-style windowed analysis. Reference
     implementation: VOICEBOX `lpcauto`.
   - *Weighted covariance method* (weighted least-squares normal equations) —
     plain covariance LPC is the all-ones-weights special case, and every
     weighted-LP GIF method in step 8 becomes just a weighting function on
     top of this one solver. Reference implementation: VOICEBOX `lpccovar`.
4. **IAIF** — iterative adaptive inverse filtering. Needed standalone *and*
   as YAGA's internal residual source, so it has to land before step 5.
5. **YAGA (GCI/GOI detection)** — the DYPSA-derived algorithm from
   `dypsagoi.m`. The largest single milestone in the project: multiscale
   wavelet product, group delay + phase-slope projection, N-best dynamic
   programming over pitch/cross-correlation/energy/slope costs, Frobenius
   norm energy term. Worth splitting into its own sub-milestones rather than
   one PR.
6. **extractVoiceFeatures** — per-cycle voice source parameters (F0, MFDR,
   CQ, NAQ, QOQ, H1-H2/HRF, etc.), built on top of step 5's GCIs/GOIs and
   step 4's glottal flow output.
7. **VUV/voicing detection** — one unified, well-tested approach, replacing
   the old codebase's two never-reconciled implementations. Also closes
   DYPSA's own bug #5 ("should have an integrated voiced/voiceless detector").
8. **Alternative weighted-LP GIF methods** — closed-phase, AME (Alku),
   and symmetric/asymmetric Gaussian weighting (Zalazar et al. 2024), as a
   comparison framework against IAIF. Thanks to step 3's weighted covariance
   solver, each method reduces to a weighting function plus config.
9. **LF-model fitting, pitch tracking (YIN), evaluation/scoring tools**
   (hit rate / miss rate / timing error against laryngograph reference).
10. **Docs, examples, first public release.**

## 10. Open items (not blocking, decide as they come up)

- Exact field list for `Signal` and other result dataclasses.
- Whether to expose a CLI in addition to the library API.
- Documentation tooling (mkdocs vs. Sphinx) for the eventual public release.
- Logistics of getting OpenGlot/APLAWD data into the validation environment.
- APLAWD is distributed in UCL's SFS (Speech Filing System) format, which may no
  longer be actively supported; VOICEBOX's `readsfs.m` is the likely reader. This
  is a long-lead dependency for the APLAWD side of Tracks A/B (see §5) — worth an
  early, low-effort probe (confirm `readsfs.m` parses one APLAWD file into
  samples/fs/EGG channel) so a format blocker surfaces with time to route around
  it, rather than at the moment the corpus is needed. OpenGlot carries no such risk
  and is therefore the natural first corpus target.
