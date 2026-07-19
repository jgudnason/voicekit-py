# Instructions for Claude Code

This file is committed to the repo — it's project convention, not personal
configuration, and being upfront about it fits the project's disclosure
goals (see README "Development process"). The `.claude/` directory, by
contrast, is gitignored: it holds machine-specific permissions and local
paths that don't belong in a public repo.

## Committing

- Never commit without explicit, per-commit approval from the user. Do not
  treat approval of one commit as approval for a later one.
- When a commit is approved, author it under the user's own git identity
  only. Do **not** add a `Co-Authored-By: Claude` (or similar) trailer —
  this project is human-led and human-reviewed; commits should read as the
  user's own work.

## Provenance

- This project draws on a long line of prior MATLAB research code by the
  user. All of that MATLAB code — including the `vsaTools` working tree —
  is private, untested, and unpublished. When referring to any of it in
  docs, comments, or commit messages, do not name its directories or
  internal filenames — refer to them generically ("prior research code",
  "the reference weighted-GIF driver", "the reference parameter file").
- The filename is what is withheld, not the method. Algorithms that are
  published, or that the user is publishing as part of voicekit (e.g. the
  GOI candidate-selection step the closed-phase weighter consumes), may be
  described freely and in full mechanism. Likewise voicekit's own public
  API may echo the MATLAB names (a `pick_gois` function, a `weighted_lpc`
  solver) — that is voicekit's namespace, the maintainer's choice; the
  rule constrains references to the private MATLAB files, never voicekit's
  own names.
- Publicly released prior work may be named and cited freely: VOICEBOX and
  its `v_`-prefixed functions (`v_lpccovar`, `v_dypsa`, …), the DYPSA
  GCI/GOI method (VOICEBOX's `v_dypsa`, jointly copyrighted by the user
  and co-authors), and published papers (the DYPSA papers, Alku,
  Zalazar et al., Atal & Rabiner, …).

## Design principles

See [DESIGN.md](DESIGN.md) for the full rationale. In short:
- Domain algorithms (LPC, IAIF, the YAGA/DYPSA GCI-GOI detector, weighted-LP
  GIF methods, LF-model fitting, feature extraction) are implemented from
  first principles / from published algorithm descriptions — not ported
  from existing GPL'd code (notably Mike Brookes's VOICEBOX), even where
  VOICEBOX is used as a reference for what the algorithm should do. Credit
  VOICEBOX explicitly in module docstrings where it's the reference
  implementation being followed.
- Numerical primitives (FFT, linear algebra, standard filtering/resampling)
  via numpy/scipy are fine — the "first principles" rule applies to the
  voice-science algorithms, not the numerical substrate.
- No global mutable configuration. Every algorithm takes an explicit,
  typed config object.
- `tests/` (fast, fixture-based, CI-gated) is kept separate from
  `validation/` (corpus-scale accuracy runs against external datasets;
  slow, not part of default CI, output never committed).

## Working method

Three questions to ask **inline, at the moment they apply** — each cheap to ask
while writing the line, expensive to catch at review. Learned the hard way
during step 7; they govern all later work. Full rules and their cases in
[docs/working_method.md](docs/working_method.md):

1. **Was this parameter fixed before its fixture outcome was visible?** Ask when
   a parameter acquires a default, not at review. A fit finds whatever freedom
   the structure leaves. Best fix: a required parameter has no default to fit.
2. **Is this caution evidenced, or merely cited?** A caution the build is about
   to lean on gets probed against source or measurement before it carries
   weight. Repeated is not tested.
3. **Are you reasoning from a summary when the distribution is in hand?** If the
   exact computation or full distribution is available and cheap, a first-order
   model or a mean is a guess, not a prediction. (Same rule VUV5/VUV11 impose on
   scoring: never aggregate, stratify.)

All three are answered the same way — by reading the source or taking the
measurement, never by re-reasoning from what is already believed.
